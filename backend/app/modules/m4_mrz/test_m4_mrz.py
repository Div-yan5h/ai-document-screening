"""
Tests for M4 — MRZ Parser + Cross-Check
=======================================
Verifies ICAO Doc 9303 parsing, checksum calculation, OCR cross-checking,
and graceful degradation.
"""

from __future__ import annotations

import os
import tempfile
import numpy as np
import pytest
from PIL import Image

from backend.app.schemas.contracts import IngestionOutput, OCROutput, MRZOutput
from backend.app.modules.m4_mrz.handler import (
    run,
    _parse_td3,
    _parse_td1,
    _verify_check_digit,
    _cross_check,
)

# Standard ICAO Doc 9303 TD3 sample test vector (Anna Maria Eriksson passport)
TD3_LINE1_VALID = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
TD3_LINE2_VALID = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"

# Corrupted check digit: change doc_number check digit at pos 9 from '6' to '7'
TD3_LINE2_CORRUPT = "L898902C37UTO7408122F1204159ZE184226B<<<<<10"


@pytest.fixture
def dummy_blank_image():
    """Create a blank image with no MRZ text and return its path."""
    arr = np.full((200, 400, 3), 240, dtype=np.uint8)
    img = Image.fromarray(arr)
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    img.save(path)
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestMRZParsingAndChecksums:
    def test_td3_valid_vector_checksum_and_fields(self):
        """Confirm checksum_valid=True and parsed fields match standard ICAO test vector."""
        parsed = _parse_td3([TD3_LINE1_VALID, TD3_LINE2_VALID])
        assert parsed is not None
        assert parsed["checksum_valid"] is True
        assert parsed["format"] == "TD3"

        fields = parsed["fields"]
        assert fields["doc_type"] == "P"
        assert fields["issuing_state"] == "UTO"
        assert fields["surname"] == "ERIKSSON"
        assert fields["given_names"] == "ANNA MARIA"
        assert fields["name"] == "ERIKSSON ANNA MARIA"
        assert fields["doc_number"] == "L898902C3"
        assert fields["nationality"] == "UTO"
        assert fields["dob"] == "1974-08-12"
        assert fields["sex"] == "F"
        assert fields["expiry_date"] == "2012-04-15"

    def test_td3_corrupt_check_digit_fails(self):
        """Confirm checksum_valid=False when check digit is modified."""
        parsed = _parse_td3([TD3_LINE1_VALID, TD3_LINE2_CORRUPT])
        assert parsed is not None
        assert parsed["checksum_valid"] is False
        assert parsed["fields"]["doc_number"] == "L898902C3"

    def test_check_digit_calculation(self):
        """Direct unit test on ICAO 7-3-1 check digit computation."""
        # 'L898902C3' check digit is 6
        assert _verify_check_digit("L898902C3", "6") is True
        assert _verify_check_digit("L898902C3", "5") is False


class TestMRZCrossCheck:
    def test_cross_check_matching_fields(self):
        """cross_check flags True for matching MRZ/OCR fields."""
        mrz_fields = {
            "name": "ERIKSSON ANNA MARIA",
            "dob": "1974-08-12",
            "doc_number": "L898902C3",
            "expiry_date": "2012-04-15",
        }
        ocr_fields = {
            "name": "ERIKSSON ANNA MARIA",
            "dob": "1974-08-12",
            "doc_number": "L898902C3",
            "expiry_date": "2012-04-15",
        }
        res = _cross_check(mrz_fields, ocr_fields)
        assert res["name_match"] is True
        assert res["dob_match"] is True
        assert res["doc_number_match"] is True
        assert res["expiry_match"] is True

    def test_cross_check_mismatched_doc_number(self):
        """cross_check correctly flags False when OCR misreads one character."""
        mrz_fields = {
            "name": "ERIKSSON ANNA MARIA",
            "dob": "1974-08-12",
            "doc_number": "L898902C3",
            "expiry_date": "2012-04-15",
        }
        ocr_fields = {
            "name": "ERIKSSON ANNA MARIA",
            "dob": "1974-08-12",
            "doc_number": "L898902C8",  # '8' instead of '3'
            "expiry_date": "2012-04-15",
        }
        res = _cross_check(mrz_fields, ocr_fields)
        assert res["doc_number_match"] is False
        assert res["name_match"] is True
        assert res["dob_match"] is True
        assert res["expiry_match"] is True


class TestMRZHandlerRun:
    def test_handler_fallback_to_raw_text(self, dummy_blank_image):
        """When image has no MRZ crop, handler recovers via OCR raw_text."""
        ingestion = IngestionOutput(
            session_id="test-session",
            doc_image_path=dummy_blank_image,
            live_photo_path="",
        )
        ocr = OCROutput(
            fields={
                "name": "ERIKSSON ANNA MARIA",
                "doc_number": "L898902C3",
                "dob": "1974-08-12",
                "expiry_date": "2012-04-15",
            },
            field_confidences={},
            raw_text=f"HEADER\n{TD3_LINE1_VALID}\n{TD3_LINE2_VALID}\nFOOTER",
        )
        out = run(ingestion, ocr)
        assert isinstance(out, MRZOutput)
        assert out.mrz_present is True
        assert out.checksum_valid is True
        assert out.cross_check["doc_number_match"] is True
        assert out.mrz_fields["doc_number"] == "L898902C3"

    def test_handler_no_mrz_present(self, dummy_blank_image):
        """When no MRZ is in image or text, returns mrz_present=False cleanly."""
        ingestion = IngestionOutput(
            session_id="test-session-none",
            doc_image_path=dummy_blank_image,
            live_photo_path="",
        )
        ocr = OCROutput(
            fields={"name": "JOHN DOE"},
            field_confidences={},
            raw_text="No MRZ data here just normal text",
        )
        out = run(ingestion, ocr)
        assert isinstance(out, MRZOutput)
        assert out.mrz_present is False
        assert out.checksum_valid is False
        assert out.mrz_fields == {}
        assert out.cross_check["doc_number_match"] is False

    def test_handler_never_raises_on_missing_or_corrupt_path(self):
        """Never raises on missing or invalid image path."""
        ingestion = IngestionOutput(
            session_id="test-bad-path",
            doc_image_path="/nonexistent/file/path.png",
            live_photo_path="",
        )
        ocr = OCROutput(
            fields={},
            field_confidences={},
            raw_text="",
        )
        out = run(ingestion, ocr)
        assert isinstance(out, MRZOutput)
        assert out.mrz_present is False
        assert out.checksum_valid is False
