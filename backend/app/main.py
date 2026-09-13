"""
FastAPI Application Entry Point
================================
Exposes the /screen endpoint and wires the orchestrator pipeline.
"""

import logging
from typing import Dict

from fastapi import FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from backend.app.orchestrator.pipeline import pipeline
from backend.app.schemas.contracts import ScreeningResult

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Document Screening API",
    description="Automated identity document verification and risk scoring engine",
    version="1.0.0",
)

# CORS Configuration
# Allows local Next.js frontend development server
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", status_code=status.HTTP_200_OK)
def health_check() -> Dict[str, str]:
    """Health check endpoint to verify backend service availability."""
    return {"status": "ok"}


@app.post("/screen", response_model=ScreeningResult, status_code=status.HTTP_200_OK)
async def screen_document(
    doc_file: UploadFile = File(..., description="Identity document image upload"),
    live_photo: UploadFile = File(..., description="Applicant live capture / selfie image upload"),
) -> ScreeningResult:
    """
    Execute full end-to-end document screening pipeline.

    Receives document and live photo uploads, triggers the orchestration
    pipeline (M1 through M9), and returns a unified ScreeningResult.
    """
    # 1. Validate uploaded files exist
    if not doc_file or not doc_file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document file ('doc_file') is required.",
        )

    if not live_photo or not live_photo.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Live photo ('live_photo') is required.",
        )

    # 2. Read bytes into memory
    try:
        doc_bytes = await doc_file.read()
    except Exception as exc:
        logger.error("Failed to read doc_file upload: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read uploaded document file.",
        )

    try:
        live_bytes = await live_photo.read()
    except Exception as exc:
        logger.error("Failed to read live_photo upload: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read uploaded live photo file.",
        )

    # 3. Validate content is non-empty
    if not doc_bytes or len(doc_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded document file is empty.",
        )

    if not live_bytes or len(live_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded live photo file is empty.",
        )

    # 4. Invoke the orchestrator pipeline
    try:
        result = pipeline(doc_bytes, live_bytes)
        return result
    except Exception as exc:
        logger.exception("Error during document screening pipeline execution: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during document screening.",
        )
