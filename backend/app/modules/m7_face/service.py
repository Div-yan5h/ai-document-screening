"""
M7 — Face Verification Service
==============================
Core business logic for facial recognition and verification.
Compares identity document portrait against live photo using InsightFace ArcFace.

Owner: P4 (Identity & Records)
"""

import logging
from typing import Any, Optional

import numpy as np

from backend.app.modules.m7_face.config import (
    BAND_LIKELY_MISMATCH,
    EMBEDDING_DIM,
    classify_band,
)
from backend.app.modules.m7_face.model import FaceModelManager, ModelInitializationError
from backend.app.modules.m7_face.preprocessing import load_image, select_primary_face
from backend.app.schemas.contracts import FaceVerificationOutput, IngestionOutput

logger = logging.getLogger(__name__)


def _failure_output() -> FaceVerificationOutput:
    """Return standard failure output for unverified/failed screening sessions."""
    return FaceVerificationOutput(
        similarity=0.0,
        match_band=BAND_LIKELY_MISMATCH,
        liveness_passed=None,
    )


def _normalize_embedding(vector: Any) -> Optional[np.ndarray]:
    """
    L2-normalize a raw embedding vector.

    Args:
        vector: 1D array or sequence representing face embedding.

    Returns:
        L2-normalized float32 numpy array of shape (512,), or None if invalid or zero-norm.
    """
    if vector is None:
        return None

    try:
        arr = np.asarray(vector, dtype=np.float32).flatten()
        if arr.size != EMBEDDING_DIM or not np.all(np.isfinite(arr)):
            logger.warning("Embedding has invalid size %s or non-finite values.", arr.size)
            return None

        norm = float(np.linalg.norm(arr))
        if norm <= 1e-12:
            logger.warning("Embedding has zero or near-zero L2 norm (%e).", norm)
            return None

        return arr / norm
    except Exception as err:
        logger.warning("Failed to L2-normalize embedding vector: %s", err)
        return None


def _extract_face_embedding(face: Any) -> Optional[np.ndarray]:
    """
    Extract raw embedding from an InsightFace candidate object or dict.

    InsightFace candidate objects typically provide a '.embedding' or '.normed_embedding' attribute.
    Also supports dictionaries with 'embedding' key for test doubles.
    """
    if face is None:
        return None

    raw_embedding = None
    if hasattr(face, "embedding"):
        raw_embedding = face.embedding
    elif hasattr(face, "normed_embedding"):
        raw_embedding = face.normed_embedding
    elif isinstance(face, dict):
        raw_embedding = face.get("embedding")
        if raw_embedding is None:
            raw_embedding = face.get("normed_embedding")

    return _normalize_embedding(raw_embedding)


def compute_scaled_similarity(doc_emb: np.ndarray, live_emb: np.ndarray) -> float:
    """
    Compute cosine similarity between normalized embeddings and scale to [0.0, 1.0].

    Formula:
        raw_cos = dot(doc_emb, live_emb)  # In [-1.0, 1.0]
        scaled = (raw_cos + 1.0) / 2.0     # Scaled to [0.0, 1.0]
        clamped = min(1.0, max(0.0, scaled))
    """
    raw_cos = float(np.dot(doc_emb, live_emb))
    scaled = (raw_cos + 1.0) / 2.0
    return float(np.clip(scaled, 0.0, 1.0))


def _process_image_for_face(analyzer: Any, image_path: str, label: str) -> Optional[np.ndarray]:
    """
    Load image from filesystem, detect face candidates using the analyzer,
    select the primary face using largest-area policy, and return normalized embedding.
    """
    try:
        image_bgr = load_image(image_path)
    except Exception as err:
        logger.warning("Failed to load %s image '%s': %s", label, image_path, err)
        return None

    try:
        detected_faces = analyzer.get(image_bgr)
    except Exception as err:
        logger.error("Face detection inference failed on %s image: %s", label, err)
        return None

    if not detected_faces:
        logger.info("Zero faces detected in %s image.", label)
        return None

    primary_face = select_primary_face(detected_faces)
    if primary_face is None:
        logger.info("No primary face resolved from %s image candidates.", label)
        return None

    embedding = _extract_face_embedding(primary_face)
    if embedding is None:
        logger.warning("Failed to extract valid embedding for primary face in %s image.", label)
        return None

    return embedding


def verify_faces(ingestion_out: IngestionOutput) -> FaceVerificationOutput:
    """
    Main entry point for M7 Face Verification.

    Processes doc_image_path and live_photo_path from IngestionOutput,
    extracts facial embeddings via InsightFace, calculates scaled cosine similarity,
    and classifies into match bands.

    Guarantees:
        - Never raises uncaught exceptions to caller.
        - Failure cases (missing image, no face, corrupted file, model failure)
          safely return (similarity=0.0, match_band="likely_mismatch", liveness_passed=None).

    Args:
        ingestion_out: IngestionOutput contract containing image paths.

    Returns:
        FaceVerificationOutput contract.
    """
    if ingestion_out is None:
        return _failure_output()

    doc_path = getattr(ingestion_out, "doc_image_path", None)
    live_path = getattr(ingestion_out, "live_photo_path", None)

    if not doc_path or not live_path:
        logger.warning("Missing doc_image_path or live_photo_path in IngestionOutput.")
        return _failure_output()

    try:
        analyzer = FaceModelManager.get_model()
    except ModelInitializationError as err:
        logger.error("FaceModelManager initialization failed: %s", err)
        return _failure_output()
    except Exception as err:
        logger.error("Unexpected error obtaining face model: %s", err)
        return _failure_output()

    try:
        # Extract embeddings for document and live photos
        doc_emb = _process_image_for_face(analyzer, doc_path, "document")
        if doc_emb is None:
            return _failure_output()

        live_emb = _process_image_for_face(analyzer, live_path, "live")
        if live_emb is None:
            return _failure_output()

        # Compute similarity and classify match band
        similarity = compute_scaled_similarity(doc_emb, live_emb)
        match_band = classify_band(similarity)

        return FaceVerificationOutput(
            similarity=similarity,
            match_band=match_band,
            liveness_passed=None,
        )

    except Exception as err:
        logger.error("Unexpected error during face verification: %s", err)
        return _failure_output()
