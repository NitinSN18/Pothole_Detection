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
    "area": 0.30,
    "texture": 0.14,
    "edge": 0.10,
    "irregularity": 0.11,
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


def _score_region(region_mask: np.ndarray, gray: np.ndarray, hsv: np.ndarray, image_area: float, confidence: float) -> Dict[str, Any]:
    """Score a single pothole region from a binary mask."""
    area_px = float(cv2.countNonZero(region_mask))
    area_ratio = area_px / image_area if image_area > 0 else 0.0

    # Nonlinear area scaling: small potholes still matter, large potholes rise quickly,
    # but we avoid a hard max-out for modest defects.
    area_feature = _clip01(np.sqrt(area_ratio * 7.0))
    area_feature = _clip01(0.68 * area_feature + 0.32 * _sigmoid(area_ratio, center=0.03, sharpness=55.0))

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
        sat_mean = float(np.mean(inside_hsv[:, 1]))
        val_mean = float(np.mean(inside_hsv[:, 2]))
        # water / wet surface: low saturation, moderate-to-high value
        if sat_mean < 92 and val_mean > 72:
            water_detected = True

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
    score = 100.0 * (0.06 + 0.94 * (raw_unit ** 1.10))

    # Visible water amplification.
    if water_detected:
        score = score * 1.20 + 5.0

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

    if water_detected and label == "Green":
        label = "Yellow"
        score = max(score, 38.0)

    if score >= 80.0:
        action_plan = "Immediate repair required"
    elif score >= 60.0:
        action_plan = "Urgent field inspection"
    elif score >= 35.0:
        action_plan = "Schedule repair soon"
    else:
        action_plan = "Monitor and reassess"

    return {
        "severity": label.upper(),
        "severity_label": label,
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
                "severity": "GREEN",
                "severity_label": "Green",
                "severity_score": 0.0,
                "composite_score": 0.0,
                "confidence": float(_clip01(confidence)),
                "water_detected": False,
                "action_plan": "Routine inspection",
                "authority": "PWD Zone 1",
                "components": {},
                "potholes": [],
            }

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Clean once to make connected components stable.
        kernel_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19))
        cleaned = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel_close)
        kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_OPEN, kernel_open)

        num_labels, labels = cv2.connectedComponents((cleaned > 0).astype(np.uint8))
        regions = []
        min_px = max(90, int(image_area * 0.00035))
        for lbl in range(1, num_labels):
            comp = (labels == lbl).astype(np.uint8) * 255
            if cv2.countNonZero(comp) >= min_px:
                regions.append(comp)

        if not regions:
            regions = [cleaned]

        potholes: List[Dict[str, Any]] = []
        for idx, region_mask in enumerate(regions):
            region_score = _score_region(region_mask, gray, hsv, image_area, confidence)
            region_score["index"] = idx
            potholes.append(region_score)

        # Use the highest scoring pothole as the overall summary.
        overall = max(potholes, key=lambda x: x["composite_score"])

        return {
            "severity": overall["severity"],
            "severity_label": overall["severity_label"],
            "severity_score": overall["severity_score"],
            "composite_score": overall["composite_score"],
            "confidence": float(_clip01(confidence)),
            "water_detected": overall["water_detected"],
            "action_plan": overall["action_plan"],
            "authority": overall["authority"],
            "components": overall["components"],
            "potholes": potholes,
        }

    except Exception as e:
        return {
            "severity": "GREEN",
            "severity_label": "Green",
            "severity_score": 0.0,
            "composite_score": 0.0,
            "confidence": float(_clip01(confidence)),
            "water_detected": False,
            "action_plan": "Monitor and reassess",
            "authority": "PWD Zone 1",
            "components": {},
            "potholes": [],
            "error": str(e),
        }


if __name__ == "__main__":
    print("backend/severity_engine.py: import and call compute_severity_from_mask(mask_b64, confidence, image_bytes)")
