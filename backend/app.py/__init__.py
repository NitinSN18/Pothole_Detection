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

from ..inference import infer_image_bytes
from ..severity_engine import compute_severity_from_mask

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

        result = {
            "inference": infer_res,
            "severity": severity,
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

        # Placeholder for future Firebase integration: store metadata and image
        report = {
            "gps": {"lat": latitude, "lon": longitude},
            "source": source,
            "inference": infer_res,
            "severity": severity,
        }

        return JSONResponse(content={"report": report})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "trace": traceback.format_exc()})


if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=False)
