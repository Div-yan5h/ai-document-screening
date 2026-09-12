"""
M3 — OCR Handler
================
Orchestrator-facing entry point for M3 OCR extraction.
Exposes run(ingestion_out, classifier_out) -> OCROutput.

Owner: P2
"""

from typing import Union

from backend.app.modules.m3_ocr.ocr import (
    DEFAULT_DOC_TYPE,
    SUPPORTED_DOC_TYPES,
    DocumentOCR,
)
from backend.app.schemas.contracts import (
    ClassifierOutput,
    IngestionOutput,
    OCROutput,
)

# Module-level OCR instance
_ocr_engine = DocumentOCR()


def run(
    ingestion_out: Union[IngestionOutput, str],
    classifier_out: Union[ClassifierOutput, str],
) -> OCROutput:
    """
    Executes document OCR and field extraction.

    Receives:
        - ingestion_out: IngestionOutput (or image path str) containing doc_image_path
        - classifier_out: ClassifierOutput (or doc_type str) containing doc_type

    Returns:
        OCROutput: Pydantic model containing:
            - fields (Dict[str, str]): name, dob, doc_number, expiry_date, nationality, issue_date
            - field_confidences (Dict[str, float]): confidence per field (0.0 to 1.0)
            - raw_text (str): unformatted extracted text
    """
    # Extract image path safely
    if isinstance(ingestion_out, IngestionOutput):
        doc_image_path = ingestion_out.doc_image_path
    elif isinstance(ingestion_out, str):
        doc_image_path = ingestion_out
    else:
        doc_image_path = ""

    # Extract doc_type safely
    if isinstance(classifier_out, ClassifierOutput):
        doc_type = classifier_out.doc_type
    elif isinstance(classifier_out, str):
        doc_type = classifier_out
    else:
        doc_type = DEFAULT_DOC_TYPE

    if doc_type not in SUPPORTED_DOC_TYPES:
        doc_type = DEFAULT_DOC_TYPE

    fields, field_confidences, raw_text = _ocr_engine.extract(
        image_path=doc_image_path,
        doc_type=doc_type,
    )

    return OCROutput(
        fields=fields,
        field_confidences=field_confidences,
        raw_text=raw_text,
    )
