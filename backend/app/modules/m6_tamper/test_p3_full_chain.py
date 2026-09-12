"""
Integration Tests for Person 3 Scope (M4 + M5 + M6)
===================================================
Chains all three Person 3 modules the way the orchestrator will:
  1. IngestionOutput + OCROutput -> M4 (MRZ Parser) -> MRZOutput
  2. OCROutput + MRZOutput -> M5 (Rule Validation) -> RuleValidationOutput
  3. IngestionOutput + OCROutput -> M6 (Tamper Heuristic) -> TamperOutput

Verifies that all three modules execute together seamlessly, return
well-typed contract models, and gracefully degrade on corrupted or missing inputs.
"""

from __future__ import annotations

import os
import tempfile
import numpy as np
import pytest
from PIL import Image, ImageDraw

from backend.app.schemas.contracts import (
    IngestionOutput,
    OCROutput,
    MRZOutput,
    RuleValidationOutput,
    TamperOutput,
)
from backend.app.modules.m4_mrz.handler import run as m4_run
from backend.app.modules.m5_rules.handler import run as m5_run
from backend.app.modules.m6_tamper.handler import run as m6_run


# Standard ICAO TD3 passport vector with valid checksums and future expiry (2029-04-15)
TD3_LINE1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
TD3_LINE2 = "L898902C36UTO7408122F2904157ZE184226B<<<<<18"


@pytest.fixture
def synthetic_passport_image():
    """Create a synthetic rendered document image for full-pipeline testing."""
    arr = np.full((600, 800, 3), 235, dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)

    # Header / fields area
    draw.rectangle([50, 40, 750, 100], fill=(210, 210, 210))
    # Simulated text blocks
    for i in range(6):
        draw.rectangle([60, 120 + i * 35, 300, 140 + i * 35], fill=(50, 50, 50))
    # Photo placeholder
    draw.rectangle([500, 120, 720, 360], fill=(160, 180, 200))

    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(path)
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestP3FullChain:
    def test_p3_full_chain_successful_flow(self, synthetic_passport_image):
        """
        Verify the complete orchestrated flow of Person 3:
        M4 parses MRZ and produces MRZOutput ->
        M5 validates rules using M4 output ->
        M6 evaluates image tamper suspicion signals.
        """
        ingestion = IngestionOutput(
            session_id="p3-integration-session-001",
            doc_image_path=synthetic_passport_image,
            live_photo_path="",
            doc_type_hint="passport",
        )
        ocr = OCROutput(
            fields={
                "name": "ERIKSSON ANNA MARIA",
                "dob": "1974-08-12",
                "doc_number": "L898902C3",
                "expiry_date": "2029-04-15",
                "issue_date": "2020-04-15",
                "nationality": "UTO",
                "doc_type": "passport",
            },
            field_confidences={
                "name": 0.98,
                "dob": 0.95,
                "doc_number": 0.96,
                "expiry_date": 0.94,
            },
            raw_text=f"REPUBLIC OF UTOPIA PASSPORT\n{TD3_LINE1}\n{TD3_LINE2}\n",
        )

        # ── Step 1: Run M4 (MRZ Parser) ──
        m4_out = m4_run(ingestion, ocr)
        assert isinstance(m4_out, MRZOutput)
        assert m4_out.mrz_present is True
        assert m4_out.checksum_valid is True
        assert m4_out.mrz_fields["doc_number"] == "L898902C3"
        assert m4_out.cross_check["doc_number_match"] is True
        assert m4_out.cross_check["name_match"] is True

        # ── Step 2: Run M5 (Rule Validation) using M4 Output ──
        m5_out = m5_run(ocr, m4_out)
        assert isinstance(m5_out, RuleValidationOutput)
        assert m5_out.format_valid is True
        assert m5_out.is_expired is False
        assert m5_out.logic_valid is True
        assert isinstance(m5_out.flags, list)

        # ── Step 3: Run M6 (Tamper Heuristic) ──
        m6_out = m6_run(ingestion, ocr)
        assert isinstance(m6_out, TamperOutput)
        assert 0.0 <= m6_out.suspicion_score <= 1.0
        assert isinstance(m6_out.flagged_regions, list)
        assert "ela_score" in m6_out.signals
        assert "copy_move_score" in m6_out.signals
        assert "font_inconsistency_score" in m6_out.signals

    def test_p3_chain_graceful_degradation_on_missing_file(self):
        """
        Verify that all three modules degrade safely without exceptions
        when provided a nonexistent file path.
        """
        bad_ingestion = IngestionOutput(
            session_id="bad-path-session",
            doc_image_path="/nonexistent/path/image.png",
            live_photo_path="",
        )
        bad_ocr = OCROutput(fields={}, field_confidences={}, raw_text="")

        # M4 gracefully returns no MRZ
        m4_out = m4_run(bad_ingestion, bad_ocr)
        assert isinstance(m4_out, MRZOutput)
        assert m4_out.mrz_present is False
        assert m4_out.checksum_valid is False

        # M5 flags missing data without raising
        m5_out = m5_run(bad_ocr, m4_out)
        assert isinstance(m5_out, RuleValidationOutput)
        assert m5_out.format_valid is False
        assert len(m5_out.flags) > 0

        # M6 returns zero suspicion score without raising
        m6_out = m6_run(bad_ingestion, bad_ocr)
        assert isinstance(m6_out, TamperOutput)
        assert m6_out.suspicion_score == 0.0
        assert m6_out.flagged_regions == []
