"""
M7 — Face Verification (STUB)
==============================
Walking skeleton stub. Returns mock FaceVerificationOutput.
Real implementation will: detect faces, generate embeddings, compute similarity.

Owner: P4
"""

from backend.app.schemas.contracts import FaceVerificationOutput, IngestionOutput


def run(ingestion_out: IngestionOutput) -> FaceVerificationOutput:
    """
    STUB: Returns mock FaceVerificationOutput.

    Real implementation will:
    - Detect/crop face from doc photo (RetinaFace/MTCNN)
    - Detect/crop face from live photo
    - Generate embeddings (ArcFace/InsightFace)
    - Compute cosine similarity
    - Map to match bands
    """
    return FaceVerificationOutput(
        similarity=0.0,                           # STUB: zero similarity
        match_band="review",                      # STUB: default to review
        liveness_passed=None,                     # STUB: not implemented
    )
