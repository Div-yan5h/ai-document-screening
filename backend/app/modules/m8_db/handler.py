"""
M8 — DB / Blacklist Check Handler
=================================
Pipeline handler for the M8 database / blacklist check module.
Acts as a thin wrapper delegating execution to the M8 service layer.

Owner: P4 (Identity & Records)
"""

from backend.app.modules.m8_db.service import check_database
from backend.app.schemas.contracts import DBCheckOutput, MRZOutput, OCROutput


def run(mrz_out: MRZOutput, ocr_out: OCROutput) -> DBCheckOutput:
    """
    Run the M8 DB / Blacklist check for the current screening session.

    Delegates document number resolution, normalization, and MongoDB lookup
    to check_database() in service.py.
    """
    return check_database(mrz_out, ocr_out)

