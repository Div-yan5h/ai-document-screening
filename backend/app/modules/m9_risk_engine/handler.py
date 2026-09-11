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
    STUB: Returns mock RiskEngineOutput.

    Real implementation will:
    - Normalize each signal to 0–1
    - Apply weights: blacklist(0.30), expired(0.20), ocr_mrz_mismatch(0.20),
      face_mismatch(0.20), tamper_suspicion(0.10)
    - Compute risk_score = round(100 * Σ(weight_i × signal_i))
    - Band: <30 low, 30–70 medium, >70 high
    - Build reasons from signals above threshold
    """
    return RiskEngineOutput(
        risk_score=0,                             # STUB: zero risk
        risk_band="low",                          # STUB: low band
        reasons=["STUB: No real risk analysis performed"],  # STUB: placeholder
        contributions={                           # STUB: all contributions zero
            "blacklist_hit": 0.0,
            "expired": 0.0,
            "ocr_mrz_mismatch": 0.0,
            "face_mismatch": 0.0,
            "tamper_suspicion": 0.0,
        },
    )
