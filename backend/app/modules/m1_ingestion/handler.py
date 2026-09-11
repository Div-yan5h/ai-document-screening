"""
M1 — Ingestion & Preprocessing (STUB)
======================================
Walking skeleton stub. Returns mock IngestionOutput.
Real implementation will: save files, run OpenCV preprocessing.

Owner: P1
"""

import uuid

from backend.app.schemas.contracts import IngestionOutput


def run(doc_file_path: str, live_photo_path: str) -> IngestionOutput:
    """
    STUB: Accepts file paths, returns mock IngestionOutput.

    Real implementation will:
    - Save files under a generated session_id
    - Run OpenCV: grayscale → deskew → denoise → CLAHE
    - Return path to preprocessed image
    """
    session_id = f"stub-{uuid.uuid4().hex[:8]}"

    return IngestionOutput(
        session_id=session_id,
        doc_image_path=doc_file_path,       # STUB: passes through raw path
        live_photo_path=live_photo_path,     # STUB: passes through raw path
        doc_type_hint=None,                  # STUB: no hint
    )
