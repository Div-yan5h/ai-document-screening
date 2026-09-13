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

from typing import Any, Dict, Optional, Tuple, Union

from backend.app.modules.m1_ingestion import handler as m1_ingestion
from backend.app.modules.m2_classifier import handler as m2_classifier
from backend.app.modules.m3_ocr import handler as m3_ocr
from backend.app.modules.m4_mrz import handler as m4_mrz
from backend.app.modules.m5_rules import handler as m5_rules
from backend.app.modules.m6_tamper import handler as m6_tamper
from backend.app.modules.m7_face import handler as m7_face
from backend.app.modules.m8_db import handler as m8_db
from backend.app.modules.m9_risk_engine import handler as m9_risk_engine
from backend.app.schemas.contracts import (
    ClassifierOutput,
    DBCheckOutput,
    FaceVerificationOutput,
    IngestionOutput,
    MRZOutput,
    OCROutput,
    RiskEngineOutput,
    RuleValidationOutput,
    ScreeningResult,
    TamperOutput,
)


def run_ingestion(
    doc_file_path: Union[str, bytes],
    live_photo_path: Union[str, bytes],
    doc_type_hint: Optional[str] = None,
) -> IngestionOutput:
    """
    Execute M1 Ingestion & Preprocessing.
    Reads document image and live photo files into bytes and invokes M1 handler.
    """
    if isinstance(doc_file_path, str):
        with open(doc_file_path, "rb") as f:
            doc_bytes = f.read()
    else:
        doc_bytes = doc_file_path

    if isinstance(live_photo_path, str):
        with open(live_photo_path, "rb") as f:
            live_bytes = f.read()
    else:
        live_bytes = live_photo_path

    return m1_ingestion.run(doc_bytes, live_bytes, doc_type_hint=doc_type_hint)


def run_classifier(ingestion_out: IngestionOutput) -> ClassifierOutput:
    """
    Execute M2 Document Classification.
    Passes IngestionOutput to M2 handler and returns ClassifierOutput.
    """
    return m2_classifier.run(ingestion_out)


def run_ocr(
    ingestion_out: IngestionOutput,
    classifier_out: ClassifierOutput,
) -> OCROutput:
    """
    Execute M3 Document OCR & Field Extraction.
    Passes IngestionOutput and ClassifierOutput to M3 handler and returns OCROutput.
    """
    return m3_ocr.run(ingestion_out, classifier_out)


def run_mrz(
    ingestion_out: IngestionOutput,
    ocr_out: OCROutput,
) -> MRZOutput:
    """
    Execute M4 MRZ Parser & Cross-Check.
    Passes IngestionOutput and OCROutput to M4 handler and returns MRZOutput.
    """
    return m4_mrz.run(ingestion_out, ocr_out)


def run_rules(
    ocr_out: OCROutput,
    mrz_out: MRZOutput,
) -> RuleValidationOutput:
    """
    Execute M5 Rule Validation.
    Passes OCROutput and MRZOutput to M5 handler and returns RuleValidationOutput.
    """
    return m5_rules.run(ocr_out, mrz_out)


def run_tamper(
    ingestion_out: IngestionOutput,
    ocr_out: OCROutput,
) -> TamperOutput:
    """
    Execute M6 Tamper Detection.
    Passes IngestionOutput and OCROutput to M6 handler and returns TamperOutput.
    """
    return m6_tamper.run(ingestion_out, ocr_out)


def run_face_verification(
    ingestion_out: IngestionOutput,
) -> FaceVerificationOutput:
    """
    Execute M7 Face Verification.
    Passes IngestionOutput to M7 handler and returns FaceVerificationOutput.
    """
    return m7_face.run(ingestion_out)


def run_db_check(
    mrz_out: MRZOutput,
    ocr_out: OCROutput,
) -> DBCheckOutput:
    """
    Execute M8 Database / Blacklist Check.
    Passes MRZOutput and OCROutput to M8 handler and returns DBCheckOutput.
    """
    return m8_db.run(mrz_out, ocr_out)


def run_risk_engine(
    classifier_out: ClassifierOutput,
    ocr_out: OCROutput,
    mrz_out: MRZOutput,
    rules_out: RuleValidationOutput,
    tamper_out: TamperOutput,
    face_out: FaceVerificationOutput,
    db_out: DBCheckOutput,
) -> RiskEngineOutput:
    """
    Execute M9 Risk Decision Engine.
    Computes weighted risk score and risk band from all upstream module outputs.
    """
    return m9_risk_engine.run(
        classifier_out,
        ocr_out,
        mrz_out,
        rules_out,
        tamper_out,
        face_out,
        db_out,
    )


def pipeline(
    doc_file_path: Union[str, bytes],
    live_photo_path: Union[str, bytes],
) -> ScreeningResult:
    """
    Execute end-to-end document screening pipeline per Build Spec §4.

    Args:
        doc_file_path: File system path or bytes of identity document image.
        live_photo_path: File system path or bytes of applicant selfie / live capture.

    Returns:
        Unified ScreeningResult containing session_id and all module outputs (M2–M9).
    """
    # M1 Ingestion & Preprocessing
    ingestion_out = run_ingestion(doc_file_path, live_photo_path)

    # Document Understanding (M2 Classifier + M3 OCR)
    classifier_out = run_classifier(ingestion_out)
    ocr_out = run_ocr(ingestion_out, classifier_out)

    # Document Integrity (M4 MRZ + M5 Rules + M6 Tamper)
    mrz_out = run_mrz(ingestion_out, ocr_out)
    rules_out = run_rules(ocr_out, mrz_out)
    tamper_out = run_tamper(ingestion_out, ocr_out)

    # Identity & Records (M7 Face Verification + M8 Database Check)
    face_out = run_face_verification(ingestion_out)
    db_out = run_db_check(mrz_out, ocr_out)

    # M9 Risk Decision Engine
    risk_out = run_risk_engine(
        classifier_out,
        ocr_out,
        mrz_out,
        rules_out,
        tamper_out,
        face_out,
        db_out,
    )

    return ScreeningResult(
        session_id=ingestion_out.session_id,
        classifier=classifier_out,
        ocr=ocr_out,
        mrz=mrz_out,
        rules=rules_out,
        tamper=tamper_out,
        face=face_out,
        db=db_out,
        risk=risk_out,
    )


# Public pipeline execution alias
run = pipeline

