"""
M3 — Document OCR Component (PaddleOCR Integration)
===================================================
Internal OCR engine executing text recognition using PaddleOCR.

Scope (Task 3.2):
- Accepts preprocessed document image and M2 doc_type.
- Runs PaddleOCR to extract text lines and recognition confidences.
- Aggregates recognized text into raw_text.
- Records internal OCR confidence scores.
- Returns exact frozen OCROutput contract shape with placeholder fields.
- Field extraction (regex, positional heuristics) is deferred to Task 3.3.

Owner: P2
"""

import os
from typing import Dict, List, Optional, Tuple

# Preload torch on Windows to ensure clean DLL search order before Paddle
try:
    import torch  # noqa: F401
except ImportError:
    pass

from paddleocr import PaddleOCR
from backend.app.modules.m3_ocr.extractor import FieldExtractor

SUPPORTED_DOC_TYPES: Tuple[str, ...] = ("passport", "visa", "id_card", "unknown")
DEFAULT_DOC_TYPE: str = "unknown"

REQUIRED_FIELDS: Tuple[str, ...] = (
    "name",
    "dob",
    "doc_number",
    "expiry_date",
    "nationality",
    "issue_date",
)


class DocumentOCR:
    """
    Document OCR engine powered by PaddleOCR.
    Handles text recognition, confidence extraction, and error safety.
    """

    def __init__(self, lang: str = "en"):
        self.supported_doc_types = SUPPORTED_DOC_TYPES
        self.required_fields = REQUIRED_FIELDS
        self.lang = lang
        self.last_ocr_confidences: List[float] = []
        self.extractor = FieldExtractor()

        # Initialize PaddleOCR
        # Note: enable_mkldnn=False avoids CPU oneDNN PIR instruction incompatibilities
        self.ocr = PaddleOCR(
            enable_mkldnn=False,
            lang=self.lang,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )

    def extract(
        self,
        image_path: Optional[str],
        doc_type: Optional[str] = DEFAULT_DOC_TYPE,
    ) -> Tuple[Dict[str, str], Dict[str, float], str]:
        """
        Executes PaddleOCR on the given image path and extracts structured fields.

        Args:
            image_path: Path to the preprocessed document image.
            doc_type: Document classification hint from M2.

        Returns:
            Tuple of (fields, field_confidences, raw_text):
            - fields: dict with all 6 required fields populated or "" if unextracted
            - field_confidences: dict with confidences from PaddleOCR rec_scores or 0.0
            - raw_text: string of all text lines recognized by PaddleOCR
        """
        # Baseline placeholders for contract conformance
        fields = {field: "" for field in self.required_fields}
        field_confidences = {field: 0.0 for field in self.required_fields}
        self.last_ocr_confidences = []

        # Validate image path existence
        if not image_path or not os.path.exists(image_path):
            return fields, field_confidences, ""

        try:
            # Predict using PaddleOCR 3.7+ API
            res = self.ocr.predict(image_path)

            rec_texts: List[str] = []
            rec_scores: List[float] = []

            if res:
                # Format 1: PaddleOCR 3.x / paddlex dictionary output
                if isinstance(res, list) and len(res) > 0 and isinstance(res[0], dict):
                    rec_texts = res[0].get("rec_texts", []) or []
                    rec_scores = res[0].get("rec_scores", []) or []
                # Format 2: Classic PaddleOCR [[ [box, (text, score)], ... ]]
                elif isinstance(res, list) and len(res) > 0 and isinstance(res[0], list):
                    for item in res[0]:
                        if isinstance(item, (list, tuple)) and len(item) >= 2:
                            text_info = item[1]
                            if isinstance(text_info, (list, tuple)) and len(text_info) >= 2:
                                rec_texts.append(str(text_info[0]))
                                rec_scores.append(float(text_info[1]))

            # Clean and combine recognized lines
            cleaned_lines = [str(t).strip() for t in rec_texts if str(t).strip()]
            raw_text = "\n".join(cleaned_lines)

            # Store internal recognition confidences
            self.last_ocr_confidences = [float(s) for s in rec_scores]

            # Construct OCR regions pairing recognized text with recognition scores
            regions: List[Dict[str, Any]] = []
            for t, s in zip(rec_texts, rec_scores):
                s_txt = str(t).strip()
                if s_txt:
                    regions.append({"text": s_txt, "score": float(s)})

            # Extract structured fields using doc_type rules and propagate confidences
            fields, field_confidences = self.extractor.extract(regions, doc_type or DEFAULT_DOC_TYPE)

            return fields, field_confidences, raw_text

        except Exception:
            # Safe fallback if OCR inference or file decoding fails
            self.last_ocr_confidences = []
            return fields, field_confidences, ""
