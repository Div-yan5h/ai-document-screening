"""
M6 — Tamper Heuristic (STUB)
=============================
Walking skeleton stub. Returns mock TamperOutput.
Real implementation will: run ELA, copy-move detection, font consistency.

Owner: P3
"""

from backend.app.schemas.contracts import IngestionOutput, OCROutput, TamperOutput


def run(ingestion_out: IngestionOutput, ocr_out: OCROutput) -> TamperOutput:
    """
    STUB: Returns mock TamperOutput.

    Real implementation will:
    - ELA: JPEG re-save + diff → ela_score
    - Copy-move: ORB/SIFT keypoint self-matching → copy_move_score
    - Font consistency: character-height/spacing stats → font_inconsistency_score
    - Combine into suspicion_score
    """
    return TamperOutput(
        suspicion_score=0.0,                      # STUB: no suspicion
        flagged_regions=[],                       # STUB: no regions flagged
        signals={                                 # STUB: all scores zero
            "ela_score": 0.0,
            "copy_move_score": 0.0,
            "font_inconsistency_score": 0.0,
        },
    )
