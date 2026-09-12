"""
M7 — Face Verification Configuration
====================================
Centralized configuration, model settings, similarity thresholds,
and classification band mappings for the M7 Face Verification module.

Owner: P4 (Identity & Records)
"""

from typing import Tuple

# =============================================================================
# Similarity Thresholds
# =============================================================================
CONFIDENT_MATCH_THRESHOLD: float = 0.75
REVIEW_THRESHOLD: float = 0.50

# =============================================================================
# Match-Band Category Names (Aligned with Contracts schema)
# =============================================================================
BAND_CONFIDENT_MATCH: str = "confident_match"
BAND_REVIEW: str = "review"
BAND_LIKELY_MISMATCH: str = "likely_mismatch"

# =============================================================================
# InsightFace / ArcFace Model Settings
# =============================================================================
# Lightweight buffalo_s model suite (SCRFD detector + MobileFaceNet/ArcFace recognizer)
INSIGHTFACE_MODEL_NAME: str = "buffalo_s"

# Standard detection resolution for SCRFD (width, height)
DETECTION_SIZE: Tuple[int, int] = (640, 640)

# Detection confidence score threshold for qualifying face candidates
DETECTION_THRESHOLD: float = 0.50

# Default execution providers for local CPU inference via ONNX Runtime
EXECUTION_PROVIDERS: Tuple[str, ...] = ("CPUExecutionProvider",)

# ArcFace embedding vector dimensionality
EMBEDDING_DIM: int = 512


# =============================================================================
# Classification Helper
# =============================================================================
def classify_band(similarity: float) -> str:
    """
    Map a normalized cosine similarity score [0.0, 1.0] to a contract match band.

    Bands:
        similarity >= 0.75         -> "confident_match"
        0.50 <= similarity < 0.75  -> "review"
        similarity < 0.50          -> "likely_mismatch"

    Args:
        similarity: Cosine similarity score bounded between 0.0 and 1.0.

    Returns:
        One of ("confident_match", "review", "likely_mismatch").
    """
    if similarity >= CONFIDENT_MATCH_THRESHOLD:
        return BAND_CONFIDENT_MATCH
    elif similarity >= REVIEW_THRESHOLD:
        return BAND_REVIEW
    else:
        return BAND_LIKELY_MISMATCH
