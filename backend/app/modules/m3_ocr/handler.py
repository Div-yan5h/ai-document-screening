"""
M3 — OCR (STUB)
================
Walking skeleton stub. Returns mock OCROutput.
Real implementation will: run PaddleOCR + field mapping.

Owner: P2
"""

from backend.app.schemas.contracts import (
    ClassifierOutput,
    IngestionOutput,
    OCROutput,
)


def run(ingestion_out: IngestionOutput, classifier_out: ClassifierOutput) -> OCROutput:
    """
    STUB: Returns mock OCROutput with placeholder fields.

    Real implementation will:
    - Run PaddleOCR on ingestion_out.doc_image_path
    - Map raw OCR to named fields using doc_type from classifier_out
    - Attach per-field confidence from PaddleOCR box scores
    """
    return OCROutput(
        fields={                                  # STUB: placeholder mock values
            "name": "STUB_NAME",
            "dob": "1990-01-01",
            "doc_number": "STUB000000",
            "expiry_date": "2030-12-31",
            "nationality": "STUB",
            "issue_date": "2020-01-01",
        },
        field_confidences={                       # STUB: zero confidence signals mock
            "name": 0.0,
            "dob": 0.0,
            "doc_number": 0.0,
            "expiry_date": 0.0,
            "nationality": 0.0,
            "issue_date": 0.0,
        },
        raw_text="STUB RAW OCR TEXT",             # STUB: placeholder
    )
