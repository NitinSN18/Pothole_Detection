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
                            if isinstance(pts[0], list):
                                contours_out.append(pts)
                            else:
                                contours_out.append([pts])
                except Exception:
                    # fallback to polygon representation
                    if hasattr(masks, "xy"):
                        for poly_list in masks.xy:
                            for poly in poly_list:
                                poly_arr = np.array(poly).astype(np.int32)
                                cv2.fillPoly(mask_img, [poly_arr], 255)
                                contours_out.append(poly_arr.reshape(-1, 2).tolist())
            elif hasattr(masks, "xy"):
                for poly_list in masks.xy:
                    for poly in poly_list:
                        poly_arr = np.array(poly).astype(np.int32)
                        cv2.fillPoly(mask_img, [poly_arr], 255)
                        contours_out.append(poly_arr.reshape(-1, 2).tolist())

        # If no masks, try to build mask from bounding boxes
        if mask_img.sum() == 0:
            try:
                if hasattr(res, "boxes") and res.boxes is not None:
                    xyxy = getattr(res.boxes, "xyxy", None)
                    if xyxy is not None:
                        boxes = np.array(xyxy)
                        for b in boxes:
                            x1, y1, x2, y2 = [int(v) for v in b[:4]]
                            cv2.rectangle(mask_img, (x1, y1), (x2, y2), 255, -1)
                            contours_out.append([[x1, y1], [x2, y1], [x2, y2], [x1, y2]])
            except Exception:
                pass

        # Final contour extraction (combined mask)
        try:
            final_cnts, _ = cv2.findContours(mask_img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if len(final_cnts) and len(areas) == 0:
                for c in final_cnts:
                    a = float(cv2.contourArea(c))
                    areas.append(a)
                    pts = c.squeeze().tolist()
                    if isinstance(pts[0], list):
                        contours_out.append(pts)
                    else:
                        contours_out.append([pts])
        except Exception:
            pass

        # Encode mask to base64 PNG
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
    print("backend/inference.py: utility module — import and call infer_image_bytes()")
