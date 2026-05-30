"""FastAPI backend for AVISENS.

Endpoints:
- POST /predict: multipart image -> runs inference + severity
- POST /citizen-upload: multipart image + optional gps -> runs inference + severity and returns metadata
- GET /health: simple health check

This module is intentionally modular so Firebase integration can be added in `firebase_utils.py`.
"""
from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import traceback
from typing import Optional
from io import BytesIO
import cv2
import numpy as np
from PIL import Image

from backend.inference import infer_image_bytes
from backend.severity_engine import compute_severity_from_mask, score_region_mask


def _safe_contour_to_mask(contour_points, shape):
    mask = np.zeros(shape[:2], dtype=np.uint8)
    try:
        pts = np.asarray(contour_points, dtype=np.int32)
        if pts.ndim == 2 and pts.shape[1] == 2 and pts.shape[0] >= 3:
            contour = pts.reshape((-1, 1, 2))
            cv2.drawContours(mask, [contour], -1, 255, thickness=-1)
            return mask
    except Exception:
        return None
    return None


def _score_each_contour(contours, image_bytes, confidence, image_shape):
    potholes = []
    for idx, contour in enumerate(contours):
        region_mask = _safe_contour_to_mask(contour, image_shape)
        if region_mask is None or cv2.countNonZero(region_mask) == 0:
            continue
        region_score = score_region_mask(region_mask, image_bytes, confidence)
        region_score["index"] = idx
        region_score["contour"] = contour
        potholes.append(region_score)
    return potholes

app = FastAPI(title="AVISENS API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/predict")
async def predict(image: UploadFile = File(...)):
    try:
        content = await image.read()
        infer_res = infer_image_bytes(content)
        if infer_res.get("error"):
            raise RuntimeError(infer_res.get("error"))

        mask_b64 = infer_res.get("mask", "")
        confidence = float(infer_res.get("confidence", 0.0))

        severity = compute_severity_from_mask(mask_b64, confidence, content)
        contours = infer_res.get("contours", []) if isinstance(infer_res.get("contours", []), list) else []
        potholes = _score_each_contour(contours, content, confidence, np.array(Image.open(BytesIO(content)).convert("RGB")).shape)
        if potholes:
            potholes = sorted(potholes, key=lambda item: item.get("composite_score", 0.0), reverse=True)
            severity = {**severity, "potholes": potholes}

        # Compatibility response: include pothole count and concise results array
        pothole_count = len(potholes) if potholes else (len(contours) if isinstance(contours, list) else 0)
        severity_label = severity.get("severity_label") if isinstance(severity, dict) else None
        composite_score = severity.get("composite_score") if isinstance(severity, dict) else None
        action_plan = severity.get("action_plan") if isinstance(severity, dict) else None
        authority = severity.get("authority") if isinstance(severity, dict) else None

        if potholes:
            compact_results = [
                {
                    "index": item.get("index"),
                    "contour": item.get("contour"),
                    "confidence": float(item.get("confidence", infer_res.get("confidence", 0.0))),
                    "severity": item.get("severity_label", item.get("severity", "Unknown")),
                    "severity_score": float(item.get("composite_score", 0.0)),
                    "composite_score": float(item.get("composite_score", 0.0)),
                    "action_plan": item.get("action_plan"),
                    "authority": item.get("authority"),
                    "water_detected": item.get("water_detected", False),
                }
                for item in potholes
            ]
        else:
            compact_results = [{
                "confidence": float(infer_res.get("confidence", 0.0)),
                "severity": (severity_label or "Unknown"),
                "severity_score": float(composite_score) if composite_score is not None else None,
                "composite_score": float(composite_score) if composite_score is not None else None,
                "action_plan": action_plan,
                "authority": authority,
            }]

        result = {
            "inference": infer_res,
            "severity": severity,
            "potholes_detected": pothole_count,
            "results": compact_results,
        }
        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})


@app.post("/citizen-upload")
async def citizen_upload(
    image: UploadFile = File(...),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    source: Optional[str] = Form("citizen"),
):
    try:
        content = await image.read()
        infer_res = infer_image_bytes(content)
        if infer_res.get("error"):
            raise RuntimeError(infer_res.get("error"))

        mask_b64 = infer_res.get("mask", "")
        confidence = float(infer_res.get("confidence", 0.0))

        severity = compute_severity_from_mask(mask_b64, confidence, content)
        contours = infer_res.get("contours", []) if isinstance(infer_res.get("contours", []), list) else []
        potholes = _score_each_contour(contours, content, confidence, np.array(Image.open(BytesIO(content)).convert("RGB")).shape)
        if potholes:
            potholes = sorted(potholes, key=lambda item: item.get("composite_score", 0.0), reverse=True)
            severity = {**severity, "potholes": potholes}

        # Placeholder for future Firebase integration: store metadata and image
        report = {
            "gps": {"lat": latitude, "lon": longitude},
            "source": source,
            "inference": infer_res,
            "severity": severity,
            "potholes_detected": len(potholes) if potholes else (len(contours) if isinstance(contours, list) else 0),
            "results": [
                {
                    "index": item.get("index"),
                    "contour": item.get("contour"),
                    "confidence": float(item.get("confidence", infer_res.get("confidence", 0.0))),
                    "severity": item.get("severity_label", item.get("severity", "Unknown")),
                    "severity_score": float(item.get("composite_score", 0.0)),
                    "composite_score": float(item.get("composite_score", 0.0)),
                    "action_plan": item.get("action_plan"),
                    "authority": item.get("authority"),
                    "water_detected": item.get("water_detected", False),
                }
                for item in potholes
            ] if potholes else [],
        }

        return JSONResponse(content={"report": report})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})


if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=False)
