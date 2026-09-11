"""
M2 — Document Classifier (STUB)
================================
Walking skeleton stub. Returns mock ClassifierOutput.
Real implementation will: run YOLO/MobileNet/ResNet18 classification.

Owner: P2
"""

from backend.app.schemas.contracts import ClassifierOutput, IngestionOutput


def run(ingestion_out: IngestionOutput) -> ClassifierOutput:
    """
    STUB: Returns mock ClassifierOutput.

    Real implementation will:
    - Load doc_image_path from ingestion_out
    - Run classification model (YOLO / MobileNet / ResNet18)
    - Return doc_type with confidence
    """
    return ClassifierOutput(
        doc_type="passport",                 # STUB: hardcoded mock value
        doc_type_confidence=0.0,             # STUB: zero confidence signals mock
        doc_bbox=None,                       # STUB: no bounding box
    )
