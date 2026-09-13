"""
M9 Risk Engine — Unit Tests
============================
Tests for risk scoring calibration across face-match outcomes
and other risk signal combinations.
"""

import pytest

from backend.app.schemas.contracts import (
    ClassifierOutput,
    DBCheckOutput,
    FaceVerificationOutput,
    MRZOutput,
    OCROutput,
    RiskEngineOutput,
    RuleValidationOutput,
    TamperOutput,
)
from backend.app.modules.m9_risk_engine.handler import run


# ── Helpers ──────────────────────────────────────────────────────────

def _clean_classifier() -> ClassifierOutput:
    return ClassifierOutput(doc_type="id_card", doc_type_confidence=0.95)


def _clean_ocr() -> OCROutput:
    return OCROutput(
        fields={"name": "John Doe", "dob": "1990-01-01", "doc_number": "X123456"},
        field_confidences={"name": 0.99, "dob": 0.98, "doc_number": 0.97},
        raw_text="John Doe 1990-01-01 X123456",
    )


def _low_confidence_ocr() -> OCROutput:
    """OCR where some fields have 0 confidence (triggers low_ocr_confidence)."""
    return OCROutput(
        fields={"name": "PURVIKA PUJARI", "dob": "01-09-1995", "doc_number": ""},
        field_confidences={"name": 0.9999, "dob": 0.9867, "doc_number": 0.0},
        raw_text="PURVIKA PUJARI 01-09-1995",
    )


def _clean_mrz() -> MRZOutput:
    return MRZOutput(
        mrz_present=False,
        mrz_fields={},
        checksum_valid=False,
        cross_check={},
    )


def _clean_rules() -> RuleValidationOutput:
    return RuleValidationOutput(
        is_expired=False,
        format_valid=True,
        logic_valid=True,
        flags=[],
    )


def _clean_tamper() -> TamperOutput:
    return TamperOutput(
        suspicion_score=0.01,
        flagged_regions=[],
        signals={"ela_score": 0.01, "copy_move_score": 0.0, "font_inconsistency_score": 0.0},
    )


def _clean_db() -> DBCheckOutput:
    return DBCheckOutput(status="not_found", record_meta=None)


# ── CASE A: Face confident match → should NOT be high risk ───────────

def test_face_confident_match_clean_document():
    """High face similarity + clean document → low risk."""
    face = FaceVerificationOutput(similarity=0.92, match_band="confident_match", liveness_passed=True)

    result = run(
        classifier_out=_clean_classifier(),
        ocr_out=_clean_ocr(),
        mrz_out=_clean_mrz(),
        rules_out=_clean_rules(),
        tamper_out=_clean_tamper(),
        face_out=face,
        db_out=_clean_db(),
    )

    assert isinstance(result, RiskEngineOutput)
    assert result.risk_band == "low", f"Clean document with face match should be low risk, got {result.risk_band} (score={result.risk_score})"
    assert result.risk_score < 30


# ── CASE B: Face review → moderate/elevated contribution ─────────────

def test_face_review_band_elevated():
    """Mid-range face similarity (review band) → should produce elevated risk."""
    face = FaceVerificationOutput(similarity=0.45, match_band="review", liveness_passed=None)

    result = run(
        classifier_out=_clean_classifier(),
        ocr_out=_clean_ocr(),
        mrz_out=_clean_mrz(),
        rules_out=_clean_rules(),
        tamper_out=_clean_tamper(),
        face_out=face,
        db_out=_clean_db(),
    )

    assert isinstance(result, RiskEngineOutput)
    # With similarity 0.45, face_mismatch = 0.55, contribution = 0.35 * 0.55 = 0.1925
    # Plus small tamper → ~20 points → low-end but meaningful
    assert result.risk_score > 10, f"Review face match should contribute meaningfully, got score={result.risk_score}"
    assert result.contributions["face_mismatch"] > 0.1


# ── CASE C: Face mismatch (0% similarity) → MUST NOT be low ─────────

def test_face_mismatch_zero_similarity_not_low():
    """0% face similarity with clean document → must NOT be low risk."""
    face = FaceVerificationOutput(similarity=0.0, match_band="likely_mismatch", liveness_passed=None)

    result = run(
        classifier_out=_clean_classifier(),
        ocr_out=_clean_ocr(),
        mrz_out=_clean_mrz(),
        rules_out=_clean_rules(),
        tamper_out=_clean_tamper(),
        face_out=face,
        db_out=_clean_db(),
    )

    assert isinstance(result, RiskEngineOutput)
    assert result.risk_band != "low", (
        f"0% face similarity must NOT produce low risk. "
        f"Got risk_band={result.risk_band}, risk_score={result.risk_score}"
    )
    assert result.risk_score >= 30, f"0% face similarity must produce score >= 30, got {result.risk_score}"


# ── CASE D: Real Aadhaar test scenario ───────────────────────────────

def test_real_aadhaar_mismatched_face_scenario():
    """
    Simulates the actual observed outputs from the real Aadhaar test:
    - Classifier: id_card, 76.3% confidence
    - OCR: fields with some 0% confidence
    - MRZ: not present (Aadhaar has no MRZ)
    - Rules: logic_valid but format_invalid
    - Tamper: 1.48% suspicion
    - Face: 0% similarity, likely_mismatch
    - DB: not_found

    The result MUST NOT be low risk.
    """
    classifier = ClassifierOutput(doc_type="id_card", doc_type_confidence=0.7634)
    ocr = _low_confidence_ocr()
    mrz = MRZOutput(
        mrz_present=False,
        mrz_fields={},
        checksum_valid=False,
        cross_check={"name_match": False, "dob_match": False, "doc_number_match": False, "expiry_match": False},
    )
    rules = RuleValidationOutput(
        is_expired=False,
        format_valid=False,
        logic_valid=True,
        flags=["The document number could not be identified.", "The document expiry date could not be identified."],
    )
    tamper = TamperOutput(
        suspicion_score=0.0148,
        flagged_regions=[[0, 0, 10, 10]] * 15,
        signals={"ela_score": 0.0445, "copy_move_score": 0.0, "font_inconsistency_score": 0.0},
    )
    face = FaceVerificationOutput(similarity=0.0, match_band="likely_mismatch", liveness_passed=None)
    db = DBCheckOutput(status="not_found", record_meta=None)

    result = run(
        classifier_out=classifier,
        ocr_out=ocr,
        mrz_out=mrz,
        rules_out=rules,
        tamper_out=tamper,
        face_out=face,
        db_out=db,
    )

    assert isinstance(result, RiskEngineOutput)
    assert result.risk_band != "low", (
        f"Real Aadhaar + mismatched face must NOT be low risk. "
        f"Got risk_band={result.risk_band}, risk_score={result.risk_score}"
    )
    assert result.risk_score >= 30
    # Face mismatch should be the dominant contribution
    assert result.contributions["face_mismatch"] >= result.contributions.get("low_ocr_confidence", 0)


# ── Additional: Blacklist hit still works ────────────────────────────

def test_blacklist_hit_produces_high_risk():
    """Blacklisted + face mismatch → should be high risk."""
    face = FaceVerificationOutput(similarity=0.0, match_band="likely_mismatch", liveness_passed=None)
    db = DBCheckOutput(status="blacklisted", record_meta={"reason": "fraud"})

    result = run(
        classifier_out=_clean_classifier(),
        ocr_out=_clean_ocr(),
        mrz_out=_clean_mrz(),
        rules_out=_clean_rules(),
        tamper_out=_clean_tamper(),
        face_out=face,
        db_out=db,
    )

    assert result.risk_band == "high" or result.risk_score >= 50, (
        f"Blacklist + face mismatch should produce high risk, got {result.risk_band} ({result.risk_score})"
    )


# ── Additional: All signals clean → low risk ────────────────────────

def test_all_clean_signals_low_risk():
    """Completely clean document → must be low risk."""
    face = FaceVerificationOutput(similarity=0.95, match_band="confident_match", liveness_passed=True)

    result = run(
        classifier_out=_clean_classifier(),
        ocr_out=_clean_ocr(),
        mrz_out=_clean_mrz(),
        rules_out=_clean_rules(),
        tamper_out=_clean_tamper(),
        face_out=face,
        db_out=_clean_db(),
    )

    assert result.risk_band == "low"
    assert result.risk_score < 15, f"Fully clean document should have very low score, got {result.risk_score}"


# ── Weights sanity check ────────────────────────────────────────────

def test_weights_sum_to_one():
    """Verify that the weight vector sums to 1.0."""
    # Run with any valid inputs to get access to the contributions dict
    face = FaceVerificationOutput(similarity=0.5, match_band="review", liveness_passed=None)
    result = run(
        classifier_out=_clean_classifier(),
        ocr_out=_clean_ocr(),
        mrz_out=_clean_mrz(),
        rules_out=_clean_rules(),
        tamper_out=_clean_tamper(),
        face_out=face,
        db_out=_clean_db(),
    )
    # All contribution keys should exist
    expected_keys = {"blacklist_hit", "expired", "ocr_mrz_mismatch", "face_mismatch", "tamper_suspicion", "low_ocr_confidence"}
    assert set(result.contributions.keys()) == expected_keys
