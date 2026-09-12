"""
M9 — Risk Engine (STUB)
========================
Walking skeleton stub. Returns mock RiskEngineOutput.
Real implementation will: normalize signals, apply weights, compute risk score.

Owner: P5
"""

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


def run(
    classifier_out: ClassifierOutput,
    ocr_out: OCROutput,
    mrz_out: MRZOutput,
    rules_out: RuleValidationOutput,
    tamper_out: TamperOutput,
    face_out: FaceVerificationOutput,
    db_out: DBCheckOutput,
) -> RiskEngineOutput:
    """
    Compute a weighted risk score from all upstream module outputs.

    Normalizes 6 signals to 0–1, applies fixed weights (sum = 1.0),
    produces a 0–100 integer risk score, bands it, and generates
    up to 3 human-readable reasons sorted by contribution.
    """
    # ── 1. Signal normalization (each 0–1) ──────────────────────────

    blacklist_hit = 1.0 if db_out.status in ("blacklisted", "watchlist") else 0.0

    expired = 1.0 if rules_out.is_expired else 0.0

    ocr_mrz_mismatch = 0.0
    if (
        mrz_out.mrz_present
        and mrz_out.checksum_valid
        and any(v is False for v in mrz_out.cross_check.values())
    ):
        ocr_mrz_mismatch = 1.0

    face_mismatch = 1.0 - face_out.similarity

    tamper_suspicion = tamper_out.suspicion_score

    low_ocr_confidence = 0.0
    if ocr_out.field_confidences:
        min_conf = min(ocr_out.field_confidences.values())
        if min_conf < 0.7:
            low_ocr_confidence = 1.0

    # ── 2. Weights (must sum to 1.0) ────────────────────────────────

    weights = {
        "blacklist_hit": 0.30,
        "expired": 0.20,
        "ocr_mrz_mismatch": 0.15,
        "face_mismatch": 0.20,
        "tamper_suspicion": 0.10,
        "low_ocr_confidence": 0.05,
    }

    signals = {
        "blacklist_hit": blacklist_hit,
        "expired": expired,
        "ocr_mrz_mismatch": ocr_mrz_mismatch,
        "face_mismatch": face_mismatch,
        "tamper_suspicion": tamper_suspicion,
        "low_ocr_confidence": low_ocr_confidence,
    }

    # ── 3. Risk score ───────────────────────────────────────────────

    weighted_sum = sum(weights[key] * signals[key] for key in weights)
    risk_score = round(100 * weighted_sum)

    # ── 4. Risk band ───────────────────────────────────────────────

    if risk_score < 30:
        risk_band = "low"
    elif risk_score < 70:
        risk_band = "medium"
    else:
        risk_band = "high"

    # ── 5. Reason generation (signal > 0.3 threshold) ──────────────

    reason_candidates: list[tuple[float, str]] = []

    if blacklist_hit > 0.3:
        reason_candidates.append((
            weights["blacklist_hit"] * blacklist_hit,
            f"Document is {db_out.status} in immigration database",
        ))

    if expired > 0.3:
        reason_candidates.append((
            weights["expired"] * expired,
            "Document has expired",
        ))

    if ocr_mrz_mismatch > 0.3:
        mismatched_fields = [
            k for k, v in mrz_out.cross_check.items() if v is False
        ]
        reason_candidates.append((
            weights["ocr_mrz_mismatch"] * ocr_mrz_mismatch,
            f"OCR and MRZ data do not match ({', '.join(mismatched_fields)})",
        ))

    if face_mismatch > 0.3:
        similarity_pct = int(face_out.similarity * 100)
        reason_candidates.append((
            weights["face_mismatch"] * face_mismatch,
            f"Face photo does not match live photo (similarity: {similarity_pct}%)",
        ))

    if tamper_suspicion > 0.3:
        suspicion_pct = int(tamper_out.suspicion_score * 100)
        reason_candidates.append((
            weights["tamper_suspicion"] * tamper_suspicion,
            f"Possible document tampering detected (suspicion score: {suspicion_pct}%)",
        ))

    if low_ocr_confidence > 0.3:
        min_conf_pct = int(min(ocr_out.field_confidences.values()) * 100)
        reason_candidates.append((
            weights["low_ocr_confidence"] * low_ocr_confidence,
            f"Low OCR confidence on extracted fields (minimum: {min_conf_pct}%)",
        ))

    # Sort by contribution descending, take top 3
    reason_candidates.sort(key=lambda x: x[0], reverse=True)
    reasons = [text for _, text in reason_candidates[:3]]

    if not reasons:
        reasons = ["No significant risk factors detected"]

    # ── 6. Contributions breakdown ─────────────────────────────────

    contributions = {
        "blacklist_hit": weights["blacklist_hit"] * signals["blacklist_hit"],
        "expired": weights["expired"] * signals["expired"],
        "ocr_mrz_mismatch": weights["ocr_mrz_mismatch"] * signals["ocr_mrz_mismatch"],
        "face_mismatch": weights["face_mismatch"] * signals["face_mismatch"],
        "tamper_suspicion": weights["tamper_suspicion"] * signals["tamper_suspicion"],
        "low_ocr_confidence": weights["low_ocr_confidence"] * signals["low_ocr_confidence"],
    }

    # ── 7. Return ──────────────────────────────────────────────────

    return RiskEngineOutput(
        risk_score=risk_score,
        risk_band=risk_band,
        reasons=reasons,
        contributions=contributions,
    )
