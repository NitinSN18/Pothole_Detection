"""Severity engine for AVISENS.

Scores each pothole region independently and returns both per-pothole results and
an overall report summary. The score is on a 0-100 scale and uses nonlinear
feature fusion so green/yellow/red separation stays realistic.
"""
from io import BytesIO
import base64
from typing import Dict, Any, List, Tuple

import cv2
import numpy as np
from PIL import Image


WEIGHTS = {
    "depth": 0.30,
    "area": 0.25,
    "texture": 0.20,
    "edge": 0.10,
    "irregularity": 0.10,
    "confidence": 0.05,
}


def _decode_mask(mask_b64: str) -> np.ndarray:
    data = base64.b64decode(mask_b64)
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("Failed to decode mask image from base64")
    _, bw = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY)
    return bw


def decode_mask(mask_b64: str) -> np.ndarray:
    """Public helper to decode base64 mask into a binary array."""
    return _decode_mask(mask_b64)


def _load_image(image_bytes: bytes) -> np.ndarray:
    pil = Image.open(BytesIO(image_bytes)).convert("RGB")
    return np.array(pil)[:, :, ::-1].copy()


def _clip01(v: float) -> float:
    return float(max(0.0, min(1.0, v)))


def _sigmoid(x: float, center: float = 0.5, sharpness: float = 8.0) -> float:
    return float(1.0 / (1.0 + np.exp(-sharpness * (x - center))))


def _label_from_score(score_100: float) -> str:
    if score_100 < 35.0:
        return "Green"
    if score_100 < 70.0:
        return "Yellow"
    return "Red"


def _severity_class(label: str) -> str:
    mapping = {"Green": "Minor", "Yellow": "Moderate", "Red": "Critical"}
    return mapping.get(label, "Minor")


def _ensure_odd(value: int) -> int:
    return value if value % 2 == 1 else value + 1


def _kernel_size(dim: int, scale: float, min_size: int) -> int:
    size = max(min_size, int(dim * scale))
    return _ensure_odd(size)


def _clean_mask(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    h, w = mask.shape[:2]
    dim = max(h, w)
    bw = (mask > 0).astype(np.uint8) * 255

    close_k = _kernel_size(dim, 0.03, 11)
    open_k = _kernel_size(dim, 0.012, 5)
    merge_k = _kernel_size(dim, 0.018, 7)

    closed = cv2.morphologyEx(
        bw, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (close_k, close_k))
    )
    opened = cv2.morphologyEx(
        closed, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (open_k, open_k))
    )
    merged = cv2.dilate(
        opened, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (merge_k, merge_k)), iterations=1
    )
    return opened, merged


def _extract_region_masks(mask: np.ndarray, image_area: float) -> List[np.ndarray]:
    opened, merged = _clean_mask(mask)
    num_labels, labels = cv2.connectedComponents((merged > 0).astype(np.uint8))
    min_px = max(120, int(image_area * 0.00045))
    regions: List[np.ndarray] = []

    for lbl in range(1, num_labels):
        comp = (labels == lbl).astype(np.uint8) * 255
        if cv2.countNonZero(comp) < min_px:
            continue
        comp_clean = cv2.bitwise_and(comp, opened)
        if cv2.countNonZero(comp_clean) < min_px // 2:
            comp_clean = comp
        comp_clean = cv2.morphologyEx(
            comp_clean,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
        )
        regions.append(comp_clean)

    if not regions and cv2.countNonZero(opened) > 0:
        regions = [opened]

    return regions


def _mask_to_contour(region_mask: np.ndarray) -> List[List[int]]:
    cnts, _ = cv2.findContours(region_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return []
    c = max(cnts, key=cv2.contourArea)
    pts = c.reshape(-1, 2).tolist()
    return pts


def extract_pothole_regions(mask_b64: str) -> List[np.ndarray]:
    mask = _decode_mask(mask_b64)
    image_area = float(mask.shape[0] * mask.shape[1])
    return _extract_region_masks(mask, image_area)


def _score_region(region_mask: np.ndarray, gray: np.ndarray, hsv: np.ndarray, image_area: float, confidence: float) -> Dict[str, Any]:
    """Score a single pothole region from a binary mask."""
    area_px = float(cv2.countNonZero(region_mask))
    area_ratio = area_px / image_area if image_area > 0 else 0.0

    # Nonlinear area scaling: small potholes still matter, large potholes rise quickly,
    # but we avoid a hard max-out for modest defects.
    area_feature = _clip01(np.sqrt(area_ratio * 8.0))
    area_feature = _clip01(0.62 * area_feature + 0.38 * _sigmoid(area_ratio, center=0.03, sharpness=55.0))

    inside_vals = gray[region_mask == 255]
    if inside_vals.size == 0:
        depth_feature = 0.0
        texture_feature = 0.0
    else:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
        dilated = cv2.dilate(region_mask, kernel, iterations=1)
        ring = cv2.subtract(dilated, region_mask)
        ring_vals = gray[ring == 255]

        inside_mean = float(np.mean(inside_vals))
        ring_mean = float(np.mean(ring_vals)) if ring_vals.size > 0 else float(np.mean(gray))
        darkness_gap = _clip01((ring_mean - inside_mean) / 255.0)

        # Darker pits should move up but stay bounded.
        depth_feature = _clip01((darkness_gap ** 0.72) * 1.22)

        texture_var = float(np.var(inside_vals))
        texture_norm = _clip01(texture_var / (255.0 ** 2))
        texture_feature = _clip01((texture_norm ** 0.62) * 1.02)

    sobelx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(sobelx ** 2 + sobely ** 2)
    boundary = cv2.Canny(region_mask, 35, 120)
    grad_vals = grad[boundary == 255]
    edge_feature = _clip01((float(np.mean(grad_vals)) / 255.0) if grad_vals.size > 0 else 0.0)
    edge_feature = _clip01((edge_feature ** 0.75) * 1.08)

    cnts, _ = cv2.findContours(region_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    irregularity_feature = 0.0
    if cnts:
        c = max(cnts, key=cv2.contourArea)
        perim = float(cv2.arcLength(c, True))
        area = float(cv2.contourArea(c))
        if perim > 0 and area > 0:
            circularity = (4.0 * np.pi * area) / (perim ** 2)
            irregularity_feature = _clip01((1.0 - circularity) ** 0.8)
            irregularity_feature = _clip01(irregularity_feature * 1.12)

    inside_hsv = hsv[region_mask == 255]
    water_detected = False
    if inside_hsv.size > 0:
        sat = inside_hsv[:, 1]
        val = inside_hsv[:, 2]
        # HSV-based wet surface: low saturation + medium/high value
        water_pixels = (sat < 90) & (val > 70)
        water_ratio = float(np.mean(water_pixels)) if water_pixels.size > 0 else 0.0
        water_detected = water_ratio > 0.18

    conf_feature = _clip01(confidence)

    components = {
        "depth": depth_feature,
        "area": area_feature,
        "texture": texture_feature,
        "edge": edge_feature,
        "irregularity": irregularity_feature,
        "confidence": conf_feature,
    }

    # Weighted score in 0..1
    raw_unit = sum(components[k] * v for k, v in WEIGHTS.items())
    raw_unit = _clip01(raw_unit)

    # Map to 0..100 with a floor so real potholes are visible but still spread out.
    score = 100.0 * (0.08 + 0.92 * (raw_unit ** 1.05))

    # Visible water amplification.
    if water_detected:
        score = score * 1.15

    # Gentle boosts for genuinely large/deep potholes, without forcing everything to 95+.
    if area_ratio > 0.02:
        score += 2.0
    if area_ratio > 0.05:
        score += 4.0
    if area_ratio > 0.09:
        score += 6.0
    if depth_feature > 0.60:
        score += 5.0 * depth_feature

    score = float(max(0.0, min(100.0, score)))
    label = _label_from_score(score)

    large_pothole = area_ratio >= 0.02
    very_large_pothole = area_ratio >= 0.06

    if water_detected and label == "Green":
        label = "Yellow"
        score = max(score, 40.0)

    if large_pothole and label == "Green":
        label = "Yellow"
        score = max(score, 38.0)

    if very_large_pothole and label != "Red":
        label = "Red"
        score = max(score, 72.0)

    if score >= 80.0:
        action_plan = "Immediate repair required"
    elif score >= 60.0:
        action_plan = "Urgent field inspection"
    elif score >= 35.0:
        action_plan = "Schedule repair soon"
    else:
        action_plan = "Monitor and reassess"

    return {
        "severity": label,
        "severity_label": label,
        "severity_class": _severity_class(label),
        "severity_score": float(score),
        "composite_score": float(score),
        "confidence": float(_clip01(confidence)),
        "water_detected": bool(water_detected),
        "action_plan": action_plan,
        "authority": "PWD Zone 1",
        "components": components,
        "area_ratio": float(area_ratio),
    }


def score_region_mask(region_mask: np.ndarray, image_bytes: bytes, confidence: float) -> Dict[str, Any]:
    """Public helper to score a single binary pothole region mask."""
    img = _load_image(image_bytes)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    image_area = float(region_mask.shape[0] * region_mask.shape[1])
    return _score_region(region_mask, gray, hsv, image_area, confidence)


def compute_severity_from_mask(mask_b64: str, confidence: float, image_bytes: bytes) -> Dict[str, Any]:
    """Compute per-pothole scores and an overall summary from a merged binary mask."""
    try:
        mask = _decode_mask(mask_b64)
        img = _load_image(image_bytes)
        h, w = mask.shape[:2]
        image_area = float(h * w)

        if cv2.countNonZero(mask) == 0:
            return {
                "severity": "Green",
                "severity_label": "Green",
                "severity_class": "Minor",
                "severity_score": 0.0,
                "composite_score": 0.0,
                "confidence": float(_clip01(confidence)),
                "water_detected": False,
                "action_plan": "Routine inspection",
                "authority": "PWD Zone 1",
                "components": {},
                "potholes": [],
                "potholes_detected": 0,
            }

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        regions = _extract_region_masks(mask, image_area)

        potholes: List[Dict[str, Any]] = []
        for idx, region_mask in enumerate(regions):
            region_score = _score_region(region_mask, gray, hsv, image_area, confidence)
            region_score["index"] = idx
            region_score["contour"] = _mask_to_contour(region_mask)
            potholes.append(region_score)

        # Use the highest scoring pothole as the overall summary.
        overall = max(potholes, key=lambda x: x["composite_score"])

        return {
            "severity": overall["severity"],
            "severity_label": overall["severity_label"],
            "severity_class": overall.get("severity_class", _severity_class(overall["severity_label"])),
            "severity_score": overall["severity_score"],
            "composite_score": overall["composite_score"],
            "confidence": float(_clip01(confidence)),
            "water_detected": overall["water_detected"],
            "action_plan": overall["action_plan"],
            "authority": overall["authority"],
            "components": overall["components"],
            "potholes": potholes,
            "potholes_detected": len(potholes),
        }

    except Exception as e:
        return {
            "severity": "Green",
            "severity_label": "Green",
            "severity_class": "Minor",
            "severity_score": 0.0,
            "composite_score": 0.0,
            "confidence": float(_clip01(confidence)),
            "water_detected": False,
            "action_plan": "Monitor and reassess",
            "authority": "PWD Zone 1",
            "components": {},
            "potholes": [],
            "potholes_detected": 0,
            "error": str(e),
        }


if __name__ == "__main__":
    print("backend/severity_engine.py: import and call compute_severity_from_mask(mask_b64, confidence, image_bytes)")
