"""
M7 — Face Verification Handler
==============================
Pipeline handler for the M7 face verification module.
Acts as a thin wrapper delegating execution to the M7 service layer.

Owner: P4 (Identity & Records)
"""

from backend.app.modules.m7_face.service import verify_faces
from backend.app.schemas.contracts import FaceVerificationOutput, IngestionOutput


def run(ingestion_out: IngestionOutput) -> FaceVerificationOutput:
    """
    Run M7 Face Verification for the current screening session.

    Delegates image loading, face detection, embedding extraction,
    and similarity scoring to verify_faces() in service.py.

    Args:
        ingestion_out: IngestionOutput contract containing doc_image_path and live_photo_path.

    Returns:
        FaceVerificationOutput contract (similarity, match_band, liveness_passed).
    """
    return verify_faces(ingestion_out)

