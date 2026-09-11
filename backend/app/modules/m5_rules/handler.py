"""
M5 — Rule Validation (STUB)
============================
Walking skeleton stub. Returns mock RuleValidationOutput.
Real implementation will: check expiry, logical consistency, format.

Owner: P3
"""

from backend.app.schemas.contracts import MRZOutput, OCROutput, RuleValidationOutput


def run(ocr_out: OCROutput, mrz_out: MRZOutput) -> RuleValidationOutput:
    """
    STUB: Returns mock RuleValidationOutput.

    Real implementation will:
    - Check expiry_date < today
    - Check issue_date < expiry_date, plausible dob
    - Check doc_number format for doc_type
    - Populate flags with plain-English reasons
    """
    return RuleValidationOutput(
        is_expired=False,                         # STUB: not expired
        format_valid=True,                        # STUB: format OK
        logic_valid=True,                         # STUB: logic OK
        flags=["STUB: No real validation performed"],  # STUB: placeholder flag
    )
