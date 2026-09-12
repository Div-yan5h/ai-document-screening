"""
M7 — Face Verification Service Unit Tests
==========================================
Unit test suite for M7 Face Verification service layer.
Tests all matching bands, edge cases, multi-face selection, and error recovery
using mock analyzers and synthetic embeddings without requiring InsightFace weights,
network access, or GPU.

Owner: P4 (Identity & Records)
"""

import os
import tempfile
from typing import Any, List, Optional

import cv2
import numpy as np
import pytest

from backend.app.modules.m7_face.config import (
    BAND_CONFIDENT_MATCH,
    BAND_LIKELY_MISMATCH,
    BAND_REVIEW,
    EMBEDDING_DIM,
)
from backend.app.modules.m7_face.model import FaceModelManager
from backend.app.modules.m7_face.service import verify_faces
from backend.app.schemas.contracts import FaceVerificationOutput, IngestionOutput


# =============================================================================
# Test Doubles (Fake Analyzer & Fake Face)
# =============================================================================

class FakeFace:
    """Mock InsightFace candidate object exposing bbox and embedding."""

    def __init__(self, bbox: Any, embedding: Any):
        self.bbox = np.asarray(bbox, dtype=np.float32)
        self.embedding = np.asarray(embedding, dtype=np.float32)


class FakeAnalyzer:
    """
    Mock FaceAnalysis instance supporting distinct returns for document and live images.
    """

    def __init__(
        self,
        doc_faces: Optional[List[Any]] = None,
        live_faces: Optional[List[Any]] = None,
        default_faces: Optional[List[Any]] = None,
        raise_exc: Optional[Exception] = None,
    ):
        self.doc_faces = doc_faces
        self.live_faces = live_faces
        self.default_faces = default_faces or []
        self.raise_exc = raise_exc
        self.call_count: int = 0

    def get(self, img: np.ndarray) -> List[Any]:
        if self.raise_exc is not None:
            raise self.raise_exc

        self.call_count += 1
        if self.call_count == 1 and self.doc_faces is not None:
            return self.doc_faces
        elif self.call_count >= 2 and self.live_faces is not None:
            return self.live_faces
        return self.default_faces


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture(autouse=True)
def reset_face_model():
    """Ensure FaceModelManager is reset before and after each test."""
    FaceModelManager.reset()
    yield
    FaceModelManager.reset()


@pytest.fixture
def dummy_image_pair():
    """Create a pair of temporary valid synthetic BGR image files."""
    tmp_doc = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp_live = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)

    img = np.zeros((120, 120, 3), dtype=np.uint8)
    img[:, :] = (100, 140, 180)

    cv2.imwrite(tmp_doc.name, img)
    cv2.imwrite(tmp_live.name, img)

    tmp_doc.close()
    tmp_live.close()

    yield tmp_doc.name, tmp_live.name

    if os.path.exists(tmp_doc.name):
        os.remove(tmp_doc.name)
    if os.path.exists(tmp_live.name):
        os.remove(tmp_live.name)


# =============================================================================
# Unit Tests
# =============================================================================

def test_successful_match(dummy_image_pair):
    """
    Case 1: Successful Match.
    Two faces with identical normalized embeddings should yield:
    similarity ≈ 1.0, match_band='confident_match', liveness_passed=None.
    """
    doc_path, live_path = dummy_image_pair
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec[0] = 1.0

    face = FakeFace(bbox=[10, 10, 80, 80], embedding=vec)
    FaceModelManager.set_model(FakeAnalyzer(default_faces=[face]))

    inp = IngestionOutput(
        session_id="test-match",
        doc_image_path=doc_path,
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert isinstance(result, FaceVerificationOutput)
    assert result.similarity == pytest.approx(1.0, abs=1e-5)
    assert result.match_band == BAND_CONFIDENT_MATCH
    assert result.liveness_passed is None


def test_review_band(dummy_image_pair):
    """
    Case 2: Review Band.
    Orthogonal embeddings produce raw_cos = 0.0, scaled to similarity = 0.5,
    falling into match_band='review'.
    """
    doc_path, live_path = dummy_image_pair
    vec_doc = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec_doc[0] = 1.0

    vec_live = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec_live[1] = 1.0

    analyzer = FakeAnalyzer(
        doc_faces=[FakeFace([0, 0, 60, 60], vec_doc)],
        live_faces=[FakeFace([0, 0, 60, 60], vec_live)],
    )
    FaceModelManager.set_model(analyzer)

    inp = IngestionOutput(
        session_id="test-review",
        doc_image_path=doc_path,
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert isinstance(result, FaceVerificationOutput)
    assert result.similarity == pytest.approx(0.5, abs=1e-5)
    assert result.match_band == BAND_REVIEW
    assert result.liveness_passed is None


def test_likely_mismatch(dummy_image_pair):
    """
    Case 3: Likely Mismatch.
    Opposite embeddings produce raw_cos = -1.0, scaled to similarity = 0.0,
    falling into match_band='likely_mismatch'.
    """
    doc_path, live_path = dummy_image_pair
    vec_doc = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec_doc[0] = 1.0

    vec_live = -vec_doc

    analyzer = FakeAnalyzer(
        doc_faces=[FakeFace([0, 0, 50, 50], vec_doc)],
        live_faces=[FakeFace([0, 0, 50, 50], vec_live)],
    )
    FaceModelManager.set_model(analyzer)

    inp = IngestionOutput(
        session_id="test-mismatch",
        doc_image_path=doc_path,
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert isinstance(result, FaceVerificationOutput)
    assert result.similarity == pytest.approx(0.0, abs=1e-5)
    assert result.match_band == BAND_LIKELY_MISMATCH
    assert result.liveness_passed is None


def test_no_document_face(dummy_image_pair):
    """
    Case 4: No Document Face.
    Analyzer returns 0 faces for document image.
    Must return safe failure output (0.0, 'likely_mismatch').
    """
    doc_path, live_path = dummy_image_pair
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec[0] = 1.0

    analyzer = FakeAnalyzer(
        doc_faces=[],
        live_faces=[FakeFace([0, 0, 50, 50], vec)],
    )
    FaceModelManager.set_model(analyzer)

    inp = IngestionOutput(
        session_id="test-no-doc-face",
        doc_image_path=doc_path,
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert isinstance(result, FaceVerificationOutput)
    assert result.similarity == 0.0
    assert result.match_band == BAND_LIKELY_MISMATCH
    assert result.liveness_passed is None


def test_no_live_face(dummy_image_pair):
    """
    Case 5: No Live Face.
    Document has a face, but live image has 0 faces.
    Must return safe failure output (0.0, 'likely_mismatch').
    """
    doc_path, live_path = dummy_image_pair
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec[0] = 1.0

    analyzer = FakeAnalyzer(
        doc_faces=[FakeFace([0, 0, 50, 50], vec)],
        live_faces=[],
    )
    FaceModelManager.set_model(analyzer)

    inp = IngestionOutput(
        session_id="test-no-live-face",
        doc_image_path=doc_path,
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert isinstance(result, FaceVerificationOutput)
    assert result.similarity == 0.0
    assert result.match_band == BAND_LIKELY_MISMATCH
    assert result.liveness_passed is None


def test_multiple_faces_largest_selected(dummy_image_pair):
    """
    Case 6: Multiple Faces.
    Multiple face candidates with different bounding box sizes.
    Verifies that the largest bounding-box face is selected deterministically.
    """
    doc_path, live_path = dummy_image_pair

    vec_match = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec_match[0] = 1.0

    vec_wrong = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec_wrong[0] = -1.0  # Opposite vector

    # Small face (area 400), wrong embedding
    face_small = FakeFace(bbox=[0, 0, 20, 20], embedding=vec_wrong)
    # Large face (area 10000), matching embedding
    face_large = FakeFace(bbox=[0, 0, 100, 100], embedding=vec_match)
    # Medium face (area 2500), wrong embedding
    face_med = FakeFace(bbox=[10, 10, 60, 60], embedding=vec_wrong)

    analyzer = FakeAnalyzer(
        doc_faces=[face_small, face_large, face_med],
        live_faces=[FakeFace([0, 0, 80, 80], vec_match)],
    )
    FaceModelManager.set_model(analyzer)

    inp = IngestionOutput(
        session_id="test-multi-face",
        doc_image_path=doc_path,
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert isinstance(result, FaceVerificationOutput)
    # If small or med face were chosen, similarity would be 0.0.
    # Because large face was chosen, similarity is 1.0.
    assert result.similarity == pytest.approx(1.0, abs=1e-5)
    assert result.match_band == BAND_CONFIDENT_MATCH


def test_invalid_embedding_dimension(dummy_image_pair):
    """
    Case 7: Invalid Embedding Dimension.
    Candidate exposes a 256-D embedding instead of 512-D.
    Must return safe failure output.
    """
    doc_path, live_path = dummy_image_pair
    vec_invalid = np.zeros(256, dtype=np.float32)
    vec_valid = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec_valid[0] = 1.0

    analyzer = FakeAnalyzer(
        doc_faces=[FakeFace([0, 0, 50, 50], vec_invalid)],
        live_faces=[FakeFace([0, 0, 50, 50], vec_valid)],
    )
    FaceModelManager.set_model(analyzer)

    inp = IngestionOutput(
        session_id="test-invalid-dim",
        doc_image_path=doc_path,
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert isinstance(result, FaceVerificationOutput)
    assert result.similarity == 0.0
    assert result.match_band == BAND_LIKELY_MISMATCH


def test_zero_norm_embedding(dummy_image_pair):
    """
    Case 8: Zero-Norm Embedding.
    Candidate exposes an all-zero vector (norm = 0).
    Must return safe failure output.
    """
    doc_path, live_path = dummy_image_pair
    vec_zero = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec_valid = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec_valid[0] = 1.0

    analyzer = FakeAnalyzer(
        doc_faces=[FakeFace([0, 0, 50, 50], vec_zero)],
        live_faces=[FakeFace([0, 0, 50, 50], vec_valid)],
    )
    FaceModelManager.set_model(analyzer)

    inp = IngestionOutput(
        session_id="test-zero-norm",
        doc_image_path=doc_path,
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert isinstance(result, FaceVerificationOutput)
    assert result.similarity == 0.0
    assert result.match_band == BAND_LIKELY_MISMATCH


def test_non_finite_embedding(dummy_image_pair):
    """
    Case 9: Non-Finite Embedding.
    Candidate embedding contains NaN or Inf values.
    Must return safe failure output.
    """
    doc_path, live_path = dummy_image_pair
    vec_nan = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec_nan[0] = float("nan")

    vec_valid = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec_valid[0] = 1.0

    analyzer = FakeAnalyzer(
        doc_faces=[FakeFace([0, 0, 50, 50], vec_nan)],
        live_faces=[FakeFace([0, 0, 50, 50], vec_valid)],
    )
    FaceModelManager.set_model(analyzer)

    inp = IngestionOutput(
        session_id="test-nan-emb",
        doc_image_path=doc_path,
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert isinstance(result, FaceVerificationOutput)
    assert result.similarity == 0.0
    assert result.match_band == BAND_LIKELY_MISMATCH


def test_missing_image(dummy_image_pair):
    """
    Case 10: Missing Image.
    Nonexistent file path.
    Must return safe failure output without crashing.
    """
    _, live_path = dummy_image_pair
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec[0] = 1.0

    FaceModelManager.set_model(FakeAnalyzer(default_faces=[FakeFace([0, 0, 50, 50], vec)]))

    inp = IngestionOutput(
        session_id="test-missing-file",
        doc_image_path="/nonexistent/path/doc.jpg",
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert isinstance(result, FaceVerificationOutput)
    assert result.similarity == 0.0
    assert result.match_band == BAND_LIKELY_MISMATCH


def test_corrupt_image(dummy_image_pair):
    """
    Case 11: Corrupt Image.
    File exists but contains non-image garbage bytes.
    Must return safe failure output without crashing.
    """
    _, live_path = dummy_image_pair
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec[0] = 1.0

    FaceModelManager.set_model(FakeAnalyzer(default_faces=[FakeFace([0, 0, 50, 50], vec)]))

    tmp_corrupt = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp_corrupt.write(b"not a valid image format")
    tmp_corrupt.close()

    try:
        inp = IngestionOutput(
            session_id="test-corrupt-file",
            doc_image_path=tmp_corrupt.name,
            live_photo_path=live_path,
        )

        result = verify_faces(inp)

        assert isinstance(result, FaceVerificationOutput)
        assert result.similarity == 0.0
        assert result.match_band == BAND_LIKELY_MISMATCH
    finally:
        if os.path.exists(tmp_corrupt.name):
            os.remove(tmp_corrupt.name)


def test_model_inference_failure(dummy_image_pair):
    """
    Case 12: Model Inference Failure.
    Analyzer.get() raises an unexpected exception.
    Must catch error and return safe failure output.
    """
    doc_path, live_path = dummy_image_pair

    failing_analyzer = FakeAnalyzer(raise_exc=RuntimeError("Simulated ONNX inference failure"))
    FaceModelManager.set_model(failing_analyzer)

    inp = IngestionOutput(
        session_id="test-inference-failure",
        doc_image_path=doc_path,
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert isinstance(result, FaceVerificationOutput)
    assert result.similarity == 0.0
    assert result.match_band == BAND_LIKELY_MISMATCH


def test_liveness_baseline(dummy_image_pair):
    """
    Case 13: Liveness Baseline.
    Confirms that in baseline implementation, liveness_passed is strictly None.
    """
    doc_path, live_path = dummy_image_pair
    vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec[0] = 1.0

    FaceModelManager.set_model(FakeAnalyzer(default_faces=[FakeFace([0, 0, 50, 50], vec)]))

    inp = IngestionOutput(
        session_id="test-liveness",
        doc_image_path=doc_path,
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert result.liveness_passed is None


def test_malformed_bounding_box_handled_safely(dummy_image_pair):
    """
    Edge Case 14: Malformed Bounding Box.
    Candidates contain inverted coordinates ([100, 100, 10, 10] -> area 0)
    and a valid box ([0, 0, 50, 50] -> area 2500).
    Valid face must be selected.
    """
    doc_path, live_path = dummy_image_pair
    vec_valid = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec_valid[0] = 1.0

    vec_inverted = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    vec_inverted[0] = -1.0

    face_inverted = FakeFace(bbox=[100, 100, 10, 10], embedding=vec_inverted)
    face_valid = FakeFace(bbox=[0, 0, 50, 50], embedding=vec_valid)

    analyzer = FakeAnalyzer(
        doc_faces=[face_inverted, face_valid],
        live_faces=[FakeFace([0, 0, 50, 50], vec_valid)],
    )
    FaceModelManager.set_model(analyzer)

    inp = IngestionOutput(
        session_id="test-malformed-bbox",
        doc_image_path=doc_path,
        live_photo_path=live_path,
    )

    result = verify_faces(inp)

    assert result.similarity == pytest.approx(1.0, abs=1e-5)
    assert result.match_band == BAND_CONFIDENT_MATCH


def test_none_input_handled_safely():
    """
    Edge Case 15: None Ingestion Input.
    Calling verify_faces(None) returns safe failure output.
    """
    result = verify_faces(None)

    assert isinstance(result, FaceVerificationOutput)
    assert result.similarity == 0.0
    assert result.match_band == BAND_LIKELY_MISMATCH
    assert result.liveness_passed is None
