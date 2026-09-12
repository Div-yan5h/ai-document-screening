"""
M2 — Document Classifier Handler
================================
Entry point for the M2 document classifier module.
Exposes run(ingestion_out: IngestionOutput) -> ClassifierOutput.

Owner: P2
"""

from backend.app.modules.m2_classifier.classifier import (
    DEFAULT_CLASS,
    TARGET_CLASSES,
    DocumentClassifier,
)
from backend.app.schemas.contracts import ClassifierOutput, IngestionOutput

# Module-level classifier instance prepared for inference
_classifier = DocumentClassifier()


def run(ingestion_out: IngestionOutput) -> ClassifierOutput:
    """
    Executes document classification on the ingested image.

    Receives:
        ingestion_out (IngestionOutput): Output from M1 containing doc_image_path,
        session_id, live_photo_path, and optional doc_type_hint.

    Returns:
        ClassifierOutput: Pydantic model containing:
            - doc_type (str): "passport" | "visa" | "id_card" | "unknown"
            - doc_type_confidence (float): 0.0 to 1.0
            - doc_bbox (Optional[List[int]]): Bounding box coordinates or None
    """
    doc_image_path = ingestion_out.doc_image_path

    # Defensive path check: ensures M2 can be tested independently of P1
    # If the file path is empty or unreadable, the classifier safely defaults to "unknown".
    if not doc_image_path:
        return ClassifierOutput(
            doc_type=DEFAULT_CLASS,
            doc_type_confidence=0.0,
            doc_bbox=None,
        )

    # Run classifier prediction
    doc_type, confidence, doc_bbox = _classifier.predict(doc_image_path)

    # Enforce contract integrity: ensure doc_type strictly belongs to TARGET_CLASSES
    if doc_type not in TARGET_CLASSES:
        doc_type = DEFAULT_CLASS

    # Ensure confidence is clamped between 0.0 and 1.0
    confidence = max(0.0, min(1.0, float(confidence)))

    return ClassifierOutput(
        doc_type=doc_type,
        doc_type_confidence=confidence,
        doc_bbox=doc_bbox,
    )
