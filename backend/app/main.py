"""
FastAPI Application Entry Point
================================
P1 owns this file. Exposes the /screen endpoint that accepts document
and live photo uploads, runs the pipeline, and returns results.

Build Spec §3 M1: POST /screen with two files (document image, live photo).
Build Spec §3 M10: POST /decision for officer actions (audit log).
"""

import os
import tempfile

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from backend.app.orchestrator.pipeline import pipeline

app = FastAPI(
    title="AI Document Screening System",
    description="Walking skeleton — stub modules, end-to-end pipeline test.",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "0.1.0-skeleton"}


@app.post("/screen")
async def screen_document(
    document: UploadFile = File(..., description="Document image file"),
    live_photo: UploadFile = File(..., description="Live photo file"),
):
    """
    Screen a document against a live photo.

    Accepts two file uploads, runs the full M1→M9 pipeline,
    and returns the risk assessment plus raw module outputs.

    Build Spec §3 M1: POST /screen with two files.
    """
    doc_bytes = await document.read()
    live_bytes = await live_photo.read()

    # Run the full pipeline
    risk_out, raw_outputs = pipeline(doc_bytes, live_bytes)

    return JSONResponse(content={
        "risk": risk_out.model_dump(),
        "module_outputs": raw_outputs,
    })
