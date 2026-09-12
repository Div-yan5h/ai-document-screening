"""
M6 — Tamper Heuristic: handler.py
===================================
Entry point for M6.  Orchestrates three independent tamper-suspicion
signals (ELA, copy-move, font consistency) and combines them into a
single TamperOutput.

The orchestrator calls ``m6_tamper.handler.run(ingestion, ocr)`` and
nothing else.  Every other function in this module is a private
implementation detail.

Owner: P3

Hard rules enforced here:
  - This module must never crash the pipeline.  Each signal runs inside
    its own try/except and degrades to (0.0, []) on failure.
  - No output ever says "confirmed" — only "suspicion" / "flagged" /
    "inconsistent."
"""

from __future__ import annotations

import logging
from typing import List

from backend.app.schemas.contracts import IngestionOutput, OCROutput, TamperOutput

from backend.app.modules.m6_tamper import ela
from backend.app.modules.m6_tamper import copy_move
from backend.app.modules.m6_tamper import font_consistency

logger = logging.getLogger(__name__)

# Maximum number of flagged region bounding boxes to return
_MAX_REGIONS = 15


def run(ingestion_out: IngestionOutput, ocr_out: OCROutput) -> TamperOutput:
    """
    M6 — Tamper Heuristic entry point.

    Runs three independent tamper-suspicion signals against the
    document image and returns a combined TamperOutput.

    Signals:
      1. ELA (Error Level Analysis)  — JPEG re-save artefact inconsistency
      2. Copy-move                   — ORB self-matching for cloned regions
      3. Font consistency            — character-height variation

    The combined suspicion_score is the simple average of the three
    signal scores (not max — max would be too sensitive to one noisy
    signal, and M9 already down-weights this module to 0.10).

    Never raises: all three signals catch their own exceptions and
    degrade gracefully, and the handler itself also wraps the whole
    flow for safety.
    """
    image_path = ingestion_out.doc_image_path
    raw_text = ocr_out.raw_text if ocr_out else ""

    all_regions: List[List[int]] = []

    # ── Signal 1: ELA ──
    try:
        ela_score, ela_regions = ela.analyse(image_path)
    except Exception as exc:
        logger.warning("ELA signal raised unexpectedly: %s", exc)
        ela_score, ela_regions = 0.0, []
    all_regions.extend(ela_regions)

    # ── Signal 2: Copy-move ──
    try:
        cm_score, cm_regions = copy_move.analyse(image_path)
    except Exception as exc:
        logger.warning("Copy-move signal raised unexpectedly: %s", exc)
        cm_score, cm_regions = 0.0, []
    all_regions.extend(cm_regions)

    # ── Signal 3: Font consistency ──
    try:
        font_score, font_regions = font_consistency.analyse(image_path, raw_text)
    except Exception as exc:
        logger.warning("Font-consistency signal raised unexpectedly: %s", exc)
        font_score, font_regions = 0.0, []
    all_regions.extend(font_regions)

    # ── Combine ──
    suspicion_score = round((ela_score + cm_score + font_score) / 3, 4)

    # Cap flagged regions at _MAX_REGIONS
    capped_regions = all_regions[:_MAX_REGIONS]

    return TamperOutput(
        suspicion_score=suspicion_score,
        flagged_regions=capped_regions,
        signals={
            "ela_score": round(ela_score, 4),
            "copy_move_score": round(cm_score, 4),
            "font_inconsistency_score": round(font_score, 4),
        },
    )
