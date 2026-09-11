"""
M8 — DB / Blacklist Check (STUB)
=================================
Walking skeleton stub. Returns mock DBCheckOutput.
Real implementation will: query MongoDB by doc_number.

Owner: P4
"""

from backend.app.schemas.contracts import DBCheckOutput, MRZOutput, OCROutput


def run(mrz_out: MRZOutput, ocr_out: OCROutput) -> DBCheckOutput:
    """
    STUB: Returns mock DBCheckOutput.

    Real implementation will:
    - Pick doc_number: prefer MRZ value if checksum valid, else OCR value
    - Query MongoDB collection by doc_number
    - Return status from record, or "not_found" / "db_unavailable"
    """
    return DBCheckOutput(
        status="not_found",                       # STUB: no real DB to query
        record_meta=None,                         # STUB: no record metadata
    )
