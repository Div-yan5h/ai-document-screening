"""
Tests for M6 — Tamper Heuristic
=================================
Uses synthetic images generated in-test (PIL/numpy), not real specimens.

Test images:
  clean   — flat background + grid of text-like rectangles with slight
            jitter in position/size/tone (not a perfectly repeating tile).
  tampered — same base, plus (a) a smooth gradient+texture patch (standing
             in for a face photo) copy-pasted to a second location away
             from the text grid, and (b) a differently-sized text block
             dropped in, then re-saved through a lossy JPEG round-trip.
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest
from PIL import Image, ImageDraw

from backend.app.schemas.contracts import IngestionOutput, OCROutput, TamperOutput
from backend.app.modules.m6_tamper import ela, copy_move, font_consistency
from backend.app.modules.m6_tamper.handler import run


# ─────────────────────────────────────────────
# Synthetic image helpers
# ─────────────────────────────────────────────

def _make_clean_image(width: int = 800, height: int = 600) -> Image.Image:
    """
    A 'clean document': light grey background with a grid of text-like
    rectangles.  Each rectangle has slight jitter in position, size, and
    tone — NOT a perfectly identical repeating tile, so it won't read as
    self-similar by copy-move.
    """
    rng = np.random.RandomState(42)
    img = Image.new("RGB", (width, height), (240, 240, 235))
    draw = ImageDraw.Draw(img)

    # Grid of text-like rectangles in the upper portion
    for row in range(8):
        for col in range(12):
            x0 = 30 + col * 60 + rng.randint(-3, 4)
            y0 = 40 + row * 28 + rng.randint(-2, 3)
            rw = rng.randint(28, 42)
            rh = rng.randint(10, 16)
            tone = rng.randint(20, 80)
            draw.rectangle(
                [x0, y0, x0 + rw, y0 + rh],
                fill=(tone, tone, tone),
            )

    return img


def _make_tampered_image(width: int = 800, height: int = 600) -> Image.Image:
    """
    A 'tampered document': same base as clean, plus:
      (a) A smooth gradient+texture patch (simulating a photo region)
          placed at two locations — a genuine copy-paste duplicate.
      (b) A differently-sized text block dropped in (inconsistent font
          height).
    Then re-saved through a JPEG round-trip to introduce ELA artefacts.
    """
    img = _make_clean_image(width, height)
    arr = np.array(img)
    rng = np.random.RandomState(99)

    # ── (a) Smooth gradient patch — NOT high-frequency noise ──
    # Create a 90×90 gradient+texture patch (like a photo region)
    patch_h, patch_w = 90, 90
    # Horizontal gradient from dark to medium
    gradient = np.tile(
        np.linspace(60, 160, patch_w, dtype=np.uint8),
        (patch_h, 1),
    )
    # Add smooth low-frequency texture (not noise)
    xx, yy = np.meshgrid(np.arange(patch_w), np.arange(patch_h))
    texture = (20 * np.sin(xx / 8.0) * np.cos(yy / 10.0)).astype(np.int16)
    patch = np.clip(gradient.astype(np.int16) + texture, 0, 255).astype(np.uint8)
    patch_rgb = np.stack([patch, patch // 2 + 40, patch // 3 + 80], axis=2)

    # Place original at bottom-left (away from text grid)
    y_src, x_src = 420, 50
    arr[y_src:y_src + patch_h, x_src:x_src + patch_w] = patch_rgb

    # Place duplicate at bottom-right (well away from the original)
    y_dst, x_dst = 420, 600
    arr[y_dst:y_dst + patch_h, x_dst:x_dst + patch_w] = patch_rgb

    # ── (b) Differently-sized text block (font inconsistency) ──
    img2 = Image.fromarray(arr)
    draw = ImageDraw.Draw(img2)
    # Normal text rects are ~10-16px tall; drop in some 24-30px tall ones
    for i in range(5):
        x0 = 500 + i * 50 + rng.randint(-2, 3)
        y0 = 320 + rng.randint(-2, 3)
        rw = rng.randint(30, 45)
        rh = rng.randint(24, 30)  # much taller than normal
        tone = rng.randint(20, 60)
        draw.rectangle([x0, y0, x0 + rw, y0 + rh], fill=(tone, tone, tone))

    # ── JPEG round-trip ──
    import io
    buf = io.BytesIO()
    img2.save(buf, format="JPEG", quality=75)
    buf.seek(0)
    tampered = Image.open(buf).convert("RGB")

    return tampered


def _save_image(img: Image.Image, suffix: str = ".png") -> str:
    """Save a PIL image to a temp file and return the path."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    img.save(path)
    return path


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture
def clean_path():
    path = _save_image(_make_clean_image())
    yield path
    os.unlink(path)


@pytest.fixture
def tampered_path():
    path = _save_image(_make_tampered_image())
    yield path
    os.unlink(path)


@pytest.fixture
def dummy_ingestion_clean(clean_path):
    return IngestionOutput(
        session_id="test-clean",
        doc_image_path=clean_path,
        live_photo_path="",
    )


@pytest.fixture
def dummy_ingestion_tampered(tampered_path):
    return IngestionOutput(
        session_id="test-tampered",
        doc_image_path=tampered_path,
        live_photo_path="",
    )


@pytest.fixture
def dummy_ocr():
    return OCROutput(
        fields={"name": "TEST USER", "dob": "1990-01-15"},
        field_confidences={"name": 0.95, "dob": 0.90},
        raw_text="TEST USER DOB 1990-01-15",
    )


@pytest.fixture
def dummy_ingestion_missing():
    return IngestionOutput(
        session_id="test-missing",
        doc_image_path="/nonexistent/path/image.png",
        live_photo_path="",
    )


# ─────────────────────────────────────────────
# ELA tests
# ─────────────────────────────────────────────

class TestELA:
    def test_ela_clean_low_score(self, clean_path):
        score, regions = ela.analyse(clean_path)
        assert 0.0 <= score <= 1.0
        assert isinstance(regions, list)

    def test_ela_tampered_higher(self, clean_path, tampered_path):
        score_clean, _ = ela.analyse(clean_path)
        score_tampered, _ = ela.analyse(tampered_path)
        assert score_tampered > score_clean, (
            f"ELA should score tampered image higher: "
            f"tampered={score_tampered}, clean={score_clean}"
        )

    def test_ela_bad_path(self):
        score, regions = ela.analyse("/nonexistent/path.png")
        assert score == 0.0
        assert regions == []


# ─────────────────────────────────────────────
# Copy-move tests
# ─────────────────────────────────────────────

class TestCopyMove:
    def test_copy_move_clean_near_zero(self, clean_path):
        score, regions = copy_move.analyse(clean_path)
        assert score == pytest.approx(0.0, abs=0.15), (
            f"Copy-move should not flag clean text grid: score={score}"
        )

    def test_copy_move_tampered_higher(self, clean_path, tampered_path):
        score_clean, _ = copy_move.analyse(clean_path)
        score_tampered, _ = copy_move.analyse(tampered_path)
        assert score_tampered > score_clean, (
            f"Copy-move should score tampered image higher: "
            f"tampered={score_tampered}, clean={score_clean}"
        )

    def test_copy_move_bad_path(self):
        score, regions = copy_move.analyse("/nonexistent/path.png")
        assert score == 0.0
        assert regions == []


# ─────────────────────────────────────────────
# Font consistency tests
# ─────────────────────────────────────────────

class TestFontConsistency:
    def test_font_clean_low_score(self, clean_path):
        """Clean synthetic document should produce a low font inconsistency score."""
        score, regions = font_consistency.analyse(clean_path)
        assert 0.0 <= score <= 0.20
        assert isinstance(regions, list)

    def test_font_complex_genuine_low_score(self):
        """
        Genuine document with photo region, circular emblem/seal, and borders
        must not produce an artificially inflated font inconsistency score.
        """
        img = _make_clean_image(width=800, height=600)
        draw = ImageDraw.Draw(img)
        # Header text
        for i in range(8):
            draw.rectangle([100 + i * 55, 15, 100 + i * 55 + 38, 35], fill=(40, 40, 40))
        # Simulated photo region on left
        draw.rectangle([30, 320, 160, 480], fill=(180, 170, 160))
        draw.rectangle([50, 340, 140, 460], fill=(120, 110, 100))
        # Simulated circular seal on top-right
        draw.ellipse([700, 15, 760, 75], outline=(100, 80, 80), width=3)
        # Border
        draw.rectangle([10, 10, 790, 590], outline=(150, 150, 150), width=1)

        path = _save_image(img)
        try:
            score, regions = font_consistency.analyse(path)
            assert 0.0 <= score <= 0.25, f"Complex genuine document scored too high: {score}"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_font_noisy_compressed_robustness(self):
        """Lossy JPEG compression artifacts must not cause false font tampering flags."""
        img = _make_clean_image(width=800, height=600)
        draw = ImageDraw.Draw(img)
        draw.rectangle([30, 320, 160, 480], fill=(180, 170, 160))
        draw.ellipse([700, 15, 760, 75], outline=(100, 80, 80), width=3)

        import io
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=60)
        buf.seek(0)
        compressed = Image.open(buf).convert("RGB")

        path = _save_image(compressed, suffix=".jpg")
        try:
            score, regions = font_consistency.analyse(path)
            assert 0.0 <= score <= 0.25, f"Noisy compressed document scored too high: {score}"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_font_intentionally_inconsistent_spliced(self):
        """Intentionally spliced text (characters with mismatched font height in a line) must be detected."""
        img = _make_clean_image()
        draw = ImageDraw.Draw(img)
        # Splice 3 oversized characters (28px vs 13px baseline) into row 2
        for i in range(3):
            x0 = 150 + i * 60
            y0 = 96 - 6
            draw.rectangle([x0, y0, x0 + 35, y0 + 28], fill=(30, 30, 30))

        path = _save_image(img)
        try:
            score, regions = font_consistency.analyse(path)
            assert score > 0.20, f"Spliced font was not detected: score={score}"
            assert len(regions) > 0, "Spliced glyphs should be flagged"
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_font_tampered_higher_than_clean(self, clean_path, tampered_path):
        """Tampered document with mismatched rogue font block scores higher than clean document."""
        score_clean, _ = font_consistency.analyse(clean_path)
        score_tampered, regions = font_consistency.analyse(tampered_path)
        assert score_tampered > score_clean
        assert len(regions) > 0

    def test_font_bad_path(self):
        score, regions = font_consistency.analyse("/nonexistent/path.png")
        assert score == 0.0
        assert regions == []

    


# ─────────────────────────────────────────────
# Handler integration tests
# ─────────────────────────────────────────────

class TestHandler:
    def test_handler_never_raises_on_missing_path(
        self, dummy_ingestion_missing, dummy_ocr
    ):
        result = run(dummy_ingestion_missing, dummy_ocr)
        assert isinstance(result, TamperOutput)
        assert 0.0 <= result.suspicion_score <= 1.0
        assert "ela_score" in result.signals
        assert "copy_move_score" in result.signals
        assert "font_inconsistency_score" in result.signals

    def test_handler_signals_keys(self, dummy_ingestion_clean, dummy_ocr):
        result = run(dummy_ingestion_clean, dummy_ocr)
        assert set(result.signals.keys()) == {
            "ela_score",
            "copy_move_score",
            "font_inconsistency_score",
        }

    def test_handler_tampered_higher_score(
        self, dummy_ingestion_clean, dummy_ingestion_tampered, dummy_ocr
    ):
        result_clean = run(dummy_ingestion_clean, dummy_ocr)
        result_tampered = run(dummy_ingestion_tampered, dummy_ocr)
        assert result_tampered.suspicion_score > result_clean.suspicion_score, (
            f"End-to-end: tampered should score higher — "
            f"tampered={result_tampered.suspicion_score}, "
            f"clean={result_clean.suspicion_score}"
        )

    def test_handler_flagged_regions_cap(
        self, dummy_ingestion_tampered, dummy_ocr
    ):
        result = run(dummy_ingestion_tampered, dummy_ocr)
        assert len(result.flagged_regions) <= 15

    def test_handler_output_types(
        self, dummy_ingestion_tampered, dummy_ocr
    ):
        result = run(dummy_ingestion_tampered, dummy_ocr)
        assert isinstance(result, TamperOutput)
        assert isinstance(result.suspicion_score, float)
        assert isinstance(result.flagged_regions, list)
        assert isinstance(result.signals, dict)
        for region in result.flagged_regions:
            assert isinstance(region, list)
            assert len(region) == 4
            assert all(isinstance(v, int) for v in region)
