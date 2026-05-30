"""AI inference engine for AVISENS — YOLOv8 segmentation wrapper.

Responsibilities:
- load YOLOv8 segmentation model from models/best.pt
- accept image bytes, run segmentation
- extract masks and contours
- compute contour areas and confidence
- return JSON-serializable result with base64 mask

Functions:
- infer_image_bytes(image_bytes, conf_thresh=0.25, device='cpu') -> dict

This module aims to be robust to small API variations of ultralytics.
"""
from pathlib import Path
from io import BytesIO
import base64
import traceback

import cv2
import numpy as np
from PIL import Image

try:
    from ultralytics import YOLO
except Exception:
    YOLO = None

# Attempt to locate model path relative to this file
MODEL_PATH = Path(__file__).resolve().parents[2] / "models" / "best.pt"
MODEL = None


def _load_model(device: str = "cpu"):
    global MODEL
    if MODEL is not None:
        return MODEL
    if YOLO is None:
        raise RuntimeError("ultralytics package not available. Install 'ultralytics' to use inference.")
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model file not found at {MODEL_PATH}")
    MODEL = YOLO(str(MODEL_PATH))
    return MODEL


def _pil_to_bgr_array(pil_img: Image.Image) -> np.ndarray:
    rgb = pil_img.convert("RGB")
    arr = np.array(rgb)
    # convert RGB -> BGR for OpenCV
    return arr[:, :, ::-1].copy()


def _sanitize_polygon(poly) -> np.ndarray | None:
    """Convert an ultralytics polygon to a safe OpenCV contour.

    Returns contour shape (N, 1, 2) int32 or None if invalid.
    """
    try:
        arr = np.asarray(poly)
        if arr.size == 0:
            return None
        arr = np.squeeze(arr)
        if arr.ndim == 1:
            if arr.size < 6 or arr.size % 2 != 0:
                return None
            arr = arr.reshape(-1, 2)
        elif arr.ndim == 2:
            if arr.shape[1] != 2:
                if arr.shape[0] == 2 and arr.shape[1] > 2:
                    arr = arr.T
                else:
                    return None
        else:
            arr = arr.reshape(-1, 2)

        arr = arr.astype(np.float32)
        arr = arr[np.isfinite(arr).all(axis=1)]
        if arr.shape[0] < 3:
            return None

        arr = np.round(arr).astype(np.int32)
        return arr.reshape((-1, 1, 2))
    except Exception:
        return None


def infer_image_bytes(image_bytes: bytes, conf_thresh: float = 0.25, device: str = "cpu") -> dict:
    """Run YOLOv8 segmentation on image bytes and return mask, confidence and contours.

    Returns dict:
    {
        "mask": <base64 PNG string of binary mask>,
        "confidence": float (0-1),
        "contours": list of polygons (list of [x,y] points),
        "areas": list of float areas for each contour
    }
    """
    try:
        model = _load_model(device=device)

        pil = Image.open(BytesIO(image_bytes))
        img_bgr = _pil_to_bgr_array(pil)
        h, w = img_bgr.shape[:2]
        image_area = float(h * w)

        # Run model inference. ultralytics offers different call styles; handle both.
        results = None
        try:
            results = model(img_bgr, conf=conf_thresh, device=device)
        except TypeError:
            # fallback to predict
            results = model.predict(source=img_bgr, conf=conf_thresh, device=device)

        if isinstance(results, (list, tuple)):
            res = results[0]
        else:
            res = results

        # Default empty mask and outputs
        mask_img = np.zeros((h, w), dtype=np.uint8)
        contours_out = []
        areas = []
        confidence = 0.0

        # Try to read confidence from boxes if present
        try:
            if hasattr(res, "boxes") and res.boxes is not None:
                # res.boxes.conf may be a tensor-like object
                confs = getattr(res.boxes, "conf", None)
                if confs is not None:
                    try:
                        # numpy / torch compatibility
                        confidence = float(np.max(np.array(confs)).item())
                    except Exception:
                        confidence = float(np.max(confs))
        except Exception:
            confidence = 0.0

        # Extract masks if available
        if hasattr(res, "masks") and res.masks is not None:
            masks = res.masks
            # Many ultralytics versions expose `masks.data` (tensor) or `masks.xy` (polygons)
            if hasattr(masks, "data"):
                try:
                    masks_np = masks.data
                    # convert to numpy if tensor
                    masks_np = np.array(masks_np)
                    # masks_np shape: (N, H, W) typically
                    for m in masks_np:
                        mbin = (m > 0.5).astype(np.uint8) * 255
                        mask_img = cv2.bitwise_or(mask_img, mbin.astype(np.uint8))
                        cnts, _ = cv2.findContours(mbin.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                        for c in cnts:
                            area = float(cv2.contourArea(c))
                            areas.append(area)
                            pts = c.squeeze().tolist()
                            if isinstance(pts, list) and pts and isinstance(pts[0], list):
                                contours_out.append(pts)
                            elif isinstance(pts, list) and len(pts) >= 3:
                                contours_out.append([pts])
                except Exception:
                    # fallback to polygon representation
                    if hasattr(masks, "xy"):
                        for poly_list in masks.xy:
                            for poly in poly_list:
                                poly_cnt = _sanitize_polygon(poly)
                                if poly_cnt is None:
                                    continue
                                cv2.drawContours(mask_img, [poly_cnt], -1, 255, thickness=-1)
                                contours_out.append(poly_cnt.reshape(-1, 2).tolist())
            elif hasattr(masks, "xy"):
                for poly_list in masks.xy:
                    for poly in poly_list:
                        poly_cnt = _sanitize_polygon(poly)
                        if poly_cnt is None:
                            continue
                        cv2.drawContours(mask_img, [poly_cnt], -1, 255, thickness=-1)
                        contours_out.append(poly_cnt.reshape(-1, 2).tolist())

        # If no masks, try to build mask from bounding boxes
        if mask_img.sum() == 0:
            try:
                if hasattr(res, "boxes") and res.boxes is not None:
                    xyxy = getattr(res.boxes, "xyxy", None)
                    if xyxy is not None:
                        boxes = np.array(xyxy)
                        for b in boxes:
                            x1, y1, x2, y2 = [int(v) for v in b[:4]]
                            if x2 > x1 and y2 > y1:
                                cv2.rectangle(mask_img, (x1, y1), (x2, y2), 255, -1)
                                contours_out.append([[x1, y1], [x2, y1], [x2, y2], [x1, y2]])
            except Exception:
                pass

        # Post-process combined mask to merge fragmented contours and remove noise
        try:
            # ensure binary
            bw = (mask_img > 127).astype(np.uint8) * 255

            # Morphological closing to fill small holes and connect fragments
            ksize = max(15, int(max(w, h) / 100))
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (ksize, ksize))
            closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)

            # Small opening to remove noise
            kernel2 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (max(5, ksize//3), max(5, ksize//3)))
            opened = cv2.morphologyEx(closed, cv2.MORPH_OPEN, kernel2)

            # Optionally dilate slightly to merge near fragments (distance threshold)
            dilate_k = max(5, ksize//4)
            dilated = cv2.dilate(opened, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (dilate_k, dilate_k)), iterations=1)

            # Connected components on dilated mask to identify merged regions
            num_labels, labels = cv2.connectedComponents(dilated)

            merged_mask = np.zeros_like(bw)
            merged_contours = []
            merged_areas = []

            min_area_px = max(100, int(0.0005 * image_area))
            for lbl in range(1, num_labels):
                comp_mask = (labels == lbl).astype(np.uint8) * 255
                area_px = int(cv2.countNonZero(comp_mask))
                if area_px < min_area_px:
                    continue
                # create a clean component mask by intersecting with original opened to avoid excessive dilation
                comp_clean = cv2.bitwise_and(comp_mask, opened)
                if cv2.countNonZero(comp_clean) == 0:
                    comp_clean = comp_mask

                cnts, _ = cv2.findContours(comp_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if not cnts:
                    continue
                # take largest contour
                c = max(cnts, key=cv2.contourArea)
                a = float(cv2.contourArea(c))
                if a < min_area_px:
                    continue
                merged_areas.append(a)
                pts = c.squeeze().tolist()
                if isinstance(pts, list) and pts and isinstance(pts[0], list):
                    merged_contours.append(pts)
                else:
                    merged_contours.append([pts])
                cv2.drawContours(merged_mask, [c], -1, 255, -1)

            # fall back to original mask contours if merged_contours empty
            if len(merged_contours) == 0:
                final_cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for c in final_cnts:
                    a = float(cv2.contourArea(c))
                    if a < min_area_px:
                        continue
                    merged_areas.append(a)
                    pts = c.squeeze().tolist()
                    if isinstance(pts, list) and pts and isinstance(pts[0], list):
                        merged_contours.append(pts)
                    else:
                        merged_contours.append([pts])
                        cv2.drawContours(merged_mask, [c], -1, 255, -1)

            # finalize mask to return (use merged_mask or original bw)
            out_mask = merged_mask if merged_mask.sum() > 0 else bw
            _, buf = cv2.imencode(".png", out_mask)
            mask_b64 = base64.b64encode(buf.tobytes()).decode("utf-8")

            contours_out = merged_contours
            areas = merged_areas

        except Exception:
            # Encode original mask as fallback
            _, buf = cv2.imencode(".png", mask_img)
            mask_b64 = base64.b64encode(buf.tobytes()).decode("utf-8")

        return {
            "mask": mask_b64,
            "confidence": float(confidence),
            "contours": contours_out,
            "areas": areas,
        }

    except Exception as e:
        # On error, provide debug info in response
        return {
            "mask": "",
            "confidence": 0.0,
            "contours": [],
            "areas": [],
            "error": str(e),
            "trace": traceback.format_exc(),
        }


if __name__ == "__main__":
    print("backend/inference: import and call infer_image_bytes()")
