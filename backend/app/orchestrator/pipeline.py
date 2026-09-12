"""
Orchestrator — Pipeline Wiring
==============================
P1 owns this file. Calls each module's run() in the correct order,
wiring outputs → inputs per the Build Spec §4.

Integrated:
- M1 Ingestion & Preprocessing
- M2 Document Classifier
- M3 OCR
- M4 MRZ Parser & Cross-Check
- M5 Rule Validation
- M6 Tamper Detection
- M7 Face Verification (P4)
- M8 Database / Blacklist Check (P4)
- M9 Risk Engine (P5)
"""

from typing import Any, Dict, Tuple

from backend.app.modules.m1_ingestion import handler as m1_ingestion
from backend.app.modules.m2_classifier import handler as m2_classifier
from backend.app.modules.m3_ocr import handler as m3_ocr
from backend.app.modules.m4_mrz import handler as m4_mrz
from backend.app.modules.m5_rules import handler as m5_rules
from backend.app.modules.m6_tamper import handler as m6_tamper
from backend.app.modules.m7_face import handler as m7_face
from backend.app.modules.m8_db import handler as m8_db
from backend.app.modules.m9_risk_engine import handler as m9_risk_engine
from backend.app.schemas.contracts import RiskEngineOutput


def pipeline(doc_file_path: str, live_photo_path: str) -> Tuple[RiskEngineOutput, Dict[str, Any]]:
    """
    Execute end-to-end document screening pipeline per Build Spec §4.

    Args:
        doc_file_path: File system path to identity document image.
        live_photo_path: File system path to applicant selfie / live capture.

    Returns:
        Tuple containing:
        - RiskEngineOutput from M9
        - Dictionary of all intermediate module outputs for dashboard drill-down
    """
    # M1 Ingestion & Preprocessing
    ingestion_out = m1_ingestion.run(doc_file_path, live_photo_path)

    # Document Understanding (M2 Classifier + M3 OCR)
    classifier_out = m2_classifier.run(ingestion_out)
    ocr_out = m3_ocr.run(ingestion_out, classifier_out)

    # Document Integrity (M4 MRZ + M5 Rules + M6 Tamper)
    mrz_out = m4_mrz.run(ingestion_out, ocr_out)
    rules_out = m5_rules.run(ocr_out, mrz_out)
    tamper_out = m6_tamper.run(ingestion_out, ocr_out)

    # Identity & Records (M7 Face Verification + M8 Database Check)
    face_out = m7_face.run(ingestion_out)
    db_out = m8_db.run(mrz_out, ocr_out)

    # M9 Risk Decision Engine
    risk_out = m9_risk_engine.run(
        classifier_out,
        ocr_out,
        mrz_out,
        rules_out,
        tamper_out,
        face_out,
        db_out,
    )

    raw_outputs = {
        "ingestion": ingestion_out,
        "classifier": classifier_out,
        "ocr": ocr_out,
        "mrz": mrz_out,
        "rules": rules_out,
        "tamper": tamper_out,
        "face": face_out,
        "db": db_out,
    }

    return risk_out, raw_outputs


# Public pipeline execution alias
run = pipeline

