"""
Tests for M5 — Rule Validation
===============================
Verifies document expiry, format validation, logical consistency,
MRZ-preferred merging, plain-English flag generation, and graceful degradation.
"""

from __future__ import annotations

import datetime
import pytest

from backend.app.schemas.contracts import OCROutput, MRZOutput, RuleValidationOutput
from backend.app.modules.m5_rules.handler import run


def _make_ocr(
    doc_number: str = "AB1234567",
    dob: str = "1990-05-20",
    expiry_date: str = "2030-12-31",
    issue_date: str = "2020-01-01",
    doc_type: str = "passport",
) -> OCROutput:
    fields = {}
    if doc_number is not None:
        fields["doc_number"] = doc_number
    if dob is not None:
        fields["dob"] = dob
    if expiry_date is not None:
        fields["expiry_date"] = expiry_date
    if issue_date is not None:
        fields["issue_date"] = issue_date
    if doc_type is not None:
        fields["doc_type"] = doc_type

    return OCROutput(
        fields=fields,
        field_confidences={k: 0.95 for k in fields},
        raw_text="",
    )


def _make_mrz(
    mrz_present: bool = False,
    checksum_valid: bool = False,
    fields: dict | None = None,
) -> MRZOutput:
    return MRZOutput(
        mrz_present=mrz_present,
        mrz_fields=fields or {},
        checksum_valid=checksum_valid,
        cross_check={},
    )


class TestExpiryValidation:
    def test_future_expiry_not_expired(self):
        """Future expiry date sets is_expired=False."""
        future_date = (datetime.date.today() + datetime.timedelta(days=365)).isoformat()
        ocr = _make_ocr(expiry_date=future_date)
        mrz = _make_mrz()
        res = run(ocr, mrz)
        assert res.is_expired is False
        assert "The document has expired." not in res.flags

    def test_past_expiry_is_expired(self):
        """Past expiry date sets is_expired=True and adds flag."""
        past_date = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
        ocr = _make_ocr(expiry_date=past_date)
        mrz = _make_mrz()
        res = run(ocr, mrz)
        assert res.is_expired is True
        assert "The document has expired." in res.flags


class TestLogicValidation:
    def test_issue_date_after_expiry_invalid(self):
        """logic_valid=False when issue date is after expiry date."""
        ocr = _make_ocr(
            issue_date="2031-01-01",
            expiry_date="2030-01-01",
        )
        mrz = _make_mrz()
        res = run(ocr, mrz)
        assert res.logic_valid is False
        assert "The issue date is not earlier than the expiry date." in res.flags

    def test_implausible_age_future_dob(self):
        """logic_valid=False when DOB implies a negative age (future DOB)."""
        tomorrow = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        ocr = _make_ocr(dob=tomorrow)
        mrz = _make_mrz()
        res = run(ocr, mrz)
        assert res.logic_valid is False
        assert "The date of birth is not plausible." in res.flags

    def test_implausible_age_over_120(self):
        """logic_valid=False when DOB implies age > 120 years."""
        ancient = (datetime.date.today() - datetime.timedelta(days=125 * 365)).isoformat()
        ocr = _make_ocr(dob=ancient)
        mrz = _make_mrz()
        res = run(ocr, mrz)
        assert res.logic_valid is False
        assert "The date of birth is not plausible." in res.flags


class TestFormatValidation:
    def test_valid_doc_number(self):
        """Valid alphanumeric document number passes format check."""
        ocr = _make_ocr(doc_number="K12345678")
        mrz = _make_mrz()
        res = run(ocr, mrz)
        assert res.format_valid is True

    def test_malformed_doc_number_too_short(self):
        """Too-short document number fails format check."""
        ocr = _make_ocr(doc_number="AB1")
        mrz = _make_mrz()
        res = run(ocr, mrz)
        assert res.format_valid is False
        assert "The document number does not match the expected format." in res.flags

    def test_malformed_doc_number_special_characters(self):
        """Garbage / punctuation symbols in doc number fail format check."""
        ocr = _make_ocr(doc_number="AB$$##123")
        mrz = _make_mrz()
        res = run(ocr, mrz)
        assert res.format_valid is False
        assert "The document number does not match the expected format." in res.flags


class TestMRZPreferredMerging:
    def test_mrz_preferred_when_checksum_valid(self):
        """When MRZ is present and checksum is valid, values come from mrz_fields."""
        ocr = _make_ocr(doc_number="INVALID_SHORT_OCR")  # would fail format check
        # But valid MRZ has clean document number
        mrz = _make_mrz(
            mrz_present=True,
            checksum_valid=True,
            fields={
                "doc_number": "VALID12345",
                "dob": "1990-05-20",
                "expiry_date": "2030-12-31",
            },
        )
        res = run(ocr, mrz)
        # Should take doc_number from MRZ and pass format validation
        assert res.format_valid is True

    def test_fallback_to_ocr_when_checksum_invalid(self):
        """When MRZ checksum is invalid, handler falls back to OCR fields."""
        ocr = _make_ocr(doc_number="INVALID#")  # bad OCR doc_number
        # MRZ has valid doc_number but checksum_valid is False
        mrz = _make_mrz(
            mrz_present=True,
            checksum_valid=False,
            fields={
                "doc_number": "VALID12345",
                "dob": "1990-05-20",
                "expiry_date": "2030-12-31",
            },
        )
        res = run(ocr, mrz)
        # Because checksum_valid is False, MRZ is distrusted and it falls back to bad OCR
        assert res.format_valid is False
        assert "The document number does not match the expected format." in res.flags


class TestFlagsAndDegradation:
    def test_plain_english_flags_generated(self):
        """Flags contain descriptive human-readable sentences for review."""
        ocr = _make_ocr(
            doc_number="",
            expiry_date="",
            dob="",
            issue_date="",
        )
        mrz = _make_mrz()
        res = run(ocr, mrz)
        assert len(res.flags) > 0
        for flag in res.flags:
            assert isinstance(flag, str)
            assert len(flag) > 10
            assert flag.endswith(".")

    def test_never_raises_on_empty_inputs(self):
        """Handler gracefully returns RuleValidationOutput on empty OCR and MRZ."""
        empty_ocr = OCROutput(fields={}, field_confidences={}, raw_text="")
        empty_mrz = MRZOutput(
            mrz_present=False,
            mrz_fields={},
            checksum_valid=False,
            cross_check={},
        )
        res = run(empty_ocr, empty_mrz)
        assert isinstance(res, RuleValidationOutput)
        assert res.format_valid is False
        assert len(res.flags) > 0
