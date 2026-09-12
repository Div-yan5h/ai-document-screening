"""
Orchestrator — Pipeline Wiring
==============================
P1 owns this file. Calls each module's run() in the correct order,
wiring outputs → inputs per Build Spec §4.

Pipeline flow:
  M1 → M2 → M3 → (M4, M5, M6) → (M7, M8) → M9

Returns:
  - RiskEngineOutput (final risk assessment)
  - dict of all raw module outputs (for dashboard drill-down)
"""

from typing import Any, Dict, Tuple

from backend.app.modules import (
    m1_ingestion,
    m2_classifier,
    m3_ocr,
    m4_mrz,
    m5_rules,
    m6_tamper,
    m7_face,
    m8_db,
    m9_risk_engine,
)
from backend.app.schemas.contracts import RiskEngineOutput


def pipeline(
    doc_bytes: bytes,
    live_bytes: bytes,
) -> Tuple[RiskEngineOutput, Dict[str, Any]]:
    """
    Execute the full screening pipeline.

    Follows Build Spec §4 flow:
      M1 (ingestion)
      → M2 (classifier) → M3 (OCR)
      → M4 (MRZ) / M5 (rules) / M6 (tamper)   [can run in parallel]
      → M7 (face) / M8 (DB)                     [can run in parallel]
      → M9 (risk engine)

    Args:
        doc_bytes: The uploaded document image bytes.
        live_bytes: The uploaded live photo bytes.

    Returns:
        Tuple of (RiskEngineOutput, dict of all raw module outputs).
    """
    # --- Stage 1: Ingestion ---
    ingestion_out = m1_ingestion.run(doc_image_bytes=doc_bytes, live_photo_bytes=live_bytes)

    # --- Stage 2: Document Understanding ---
    classifier_out = m2_classifier.run(ingestion_out)
    ocr_out = m3_ocr.run(ingestion_out, classifier_out)

    # --- Stage 3: Document Integrity (can run in parallel) ---
    mrz_out = m4_mrz.run(ingestion_out, ocr_out)
    rules_out = m5_rules.run(ocr_out, mrz_out)
    tamper_out = m6_tamper.run(ingestion_out, ocr_out)

    # --- Stage 4: Identity & Records (can run in parallel) ---
    face_out = m7_face.run(ingestion_out)
    db_out = m8_db.run(mrz_out, ocr_out)

    # --- Stage 5: Risk Scoring ---
    risk_out = m9_risk_engine.run(
        classifier_out, ocr_out, mrz_out, rules_out, tamper_out, face_out, db_out
    )

    # Collect all raw module outputs for dashboard drill-down
    raw_outputs = {
        "ingestion": ingestion_out.model_dump(),
        "classifier": classifier_out.model_dump(),
        "ocr": ocr_out.model_dump(),
        "mrz": mrz_out.model_dump(),
        "rules": rules_out.model_dump(),
        "tamper": tamper_out.model_dump(),
        "face": face_out.model_dump(),
        "db": db_out.model_dump(),
        "risk": risk_out.model_dump(),
    }

    return risk_out, raw_outputs
