"""
Comprehensive unit tests for M2 Document Classifier (Task 3).

Validates:
1. High-confidence model prediction (>= 0.6 threshold)
2. Low-confidence model prediction (< 0.6 threshold)
3. Threshold causing unknown or fallback
4. Heuristic fallback (aspect ratio + MRZ detection for passport, id_card, visa)
5. Unknown / unclassifiable image (square / out-of-range aspect ratio)
6. Safe behavior when model weights are missing or invalid
7. Safe behavior when image is missing or unreadable
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock
from PIL import Image, ImageDraw
import torch

from backend.app.modules.m2_classifier.classifier import (
    DEFAULT_CLASS,
    DEFAULT_CONFIDENCE_THRESHOLD,
    TARGET_CLASSES,
    DocumentClassifier,
)


class TestDocumentClassifierTask3(unittest.TestCase):
    def setUp(self):
        self.classifier = DocumentClassifier(device="cpu")

    def _create_synthetic_doc(
        self,
        width: int,
        height: int,
        add_mrz: bool = False,
        color=(230, 230, 230),
    ) -> str:
        """Helper to create a temporary test image."""
        img = Image.new("RGB", (width, height), color=color)
        if add_mrz:
            draw = ImageDraw.Draw(img)
            # Simulate 2 MRZ lines in bottom 18% of the document
            y_start = int(height * 0.82)
            for x in range(10, width - 10, 8):
                draw.line([(x, y_start), (x, y_start + 12)], fill=(20, 20, 20), width=2)
                draw.line([(x, y_start + 18), (x, y_start + 30)], fill=(20, 20, 20), width=2)

        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img.save(tmp.name)
        tmp.close()
        return tmp.name

    def test_high_confidence_model_prediction(self):
        """Verify that high-confidence MobileNet prediction (>= 0.6) is returned directly."""
        doc_path = self._create_synthetic_doc(500, 500)
        try:
            clf = DocumentClassifier(device="cpu")
            clf._is_loaded = True

            # Mock model output returning high confidence (0.88) for 'passport' (index 0)
            mock_logits = torch.tensor([[5.0, 0.5, 0.2, 0.1]])  # softmax top prob ~0.98
            clf.model = MagicMock(return_value=mock_logits)

            doc_type, confidence, doc_bbox = clf.predict(doc_path)
            self.assertEqual(doc_type, "passport")
            self.assertGreaterEqual(confidence, DEFAULT_CONFIDENCE_THRESHOLD)
            self.assertIsNone(doc_bbox)
        finally:
            if os.path.exists(doc_path):
                os.remove(doc_path)

    def test_low_confidence_causes_unknown_when_no_heuristic(self):
        """Verify that low-confidence prediction (< 0.6) returns 'unknown' if heuristics cannot classify."""
        # Square image has ratio 1.0 (unclassifiable by heuristic)
        doc_path = self._create_synthetic_doc(400, 400)
        try:
            clf = DocumentClassifier(device="cpu")
            clf._is_loaded = True

            # Mock model output returning low confidence (~0.35)
            mock_logits = torch.tensor([[0.5, 0.4, 0.3, 0.2]])
            clf.model = MagicMock(return_value=mock_logits)

            doc_type, confidence, doc_bbox = clf.predict(doc_path)
            # Never return a low-confidence document type as confident
            self.assertEqual(doc_type, DEFAULT_CLASS)
            self.assertLess(confidence, DEFAULT_CONFIDENCE_THRESHOLD)
            self.assertIsNone(doc_bbox)
        finally:
            if os.path.exists(doc_path):
                os.remove(doc_path)

    def test_threshold_triggers_heuristic_fallback_for_passport(self):
        """Verify low-confidence model prediction triggers heuristic fallback for passport."""
        # Passport aspect ratio 1.42 with MRZ bottom lines
        doc_path = self._create_synthetic_doc(568, 400, add_mrz=True)
        try:
            clf = DocumentClassifier(device="cpu")
            clf._is_loaded = True

            # Model gives low confidence (0.35)
            mock_logits = torch.tensor([[0.5, 0.4, 0.3, 0.2]])
            clf.model = MagicMock(return_value=mock_logits)

            doc_type, confidence, doc_bbox = clf.predict(doc_path)
            # Heuristic fallback identifies passport with confidence >= 0.6
            self.assertEqual(doc_type, "passport")
            self.assertGreaterEqual(confidence, DEFAULT_CONFIDENCE_THRESHOLD)
            self.assertIsNone(doc_bbox)
        finally:
            if os.path.exists(doc_path):
                os.remove(doc_path)

    def test_heuristic_fallback_id_card(self):
        """Verify heuristic fallback identifies ID card based on TD1 aspect ratio (~1.59)."""
        # ID Card: 636x400 -> ratio 1.59
        doc_path = self._create_synthetic_doc(636, 400, add_mrz=False)
        try:
            # Model weights unavailable (unloaded)
            clf = DocumentClassifier(device="cpu")
            doc_type, confidence, doc_bbox = clf.predict(doc_path)

            self.assertEqual(doc_type, "id_card")
            self.assertGreaterEqual(confidence, DEFAULT_CONFIDENCE_THRESHOLD)
            self.assertIsNone(doc_bbox)
        finally:
            if os.path.exists(doc_path):
                os.remove(doc_path)

    def test_heuristic_fallback_visa(self):
        """Verify heuristic fallback identifies visa based on TD2/sticker aspect ratio (~1.25)."""
        # Visa: 500x400 -> ratio 1.25
        doc_path = self._create_synthetic_doc(500, 400, add_mrz=False)
        try:
            clf = DocumentClassifier(device="cpu")
            doc_type, confidence, doc_bbox = clf.predict(doc_path)

            self.assertEqual(doc_type, "visa")
            self.assertGreaterEqual(confidence, DEFAULT_CONFIDENCE_THRESHOLD)
            self.assertIsNone(doc_bbox)
        finally:
            if os.path.exists(doc_path):
                os.remove(doc_path)

    def test_unknown_unclassifiable_image(self):
        """Verify an unclassifiable image (square 1.0 aspect ratio) returns ('unknown', 0.0, None)."""
        doc_path = self._create_synthetic_doc(350, 350, add_mrz=False)
        try:
            clf = DocumentClassifier(device="cpu")
            doc_type, confidence, doc_bbox = clf.predict(doc_path)

            self.assertEqual(doc_type, DEFAULT_CLASS)
            self.assertEqual(confidence, 0.0)
            self.assertIsNone(doc_bbox)
        finally:
            if os.path.exists(doc_path):
                os.remove(doc_path)

    def test_missing_model_weights_safe_behavior(self):
        """Verify that nonexistent model weights do not crash and fall back safely."""
        clf = DocumentClassifier(model_path="nonexistent_weights.pth", device="cpu")
        self.assertFalse(clf._is_loaded)

        # Predict with a valid ID card image falls back to heuristic
        doc_path = self._create_synthetic_doc(636, 400)
        try:
            doc_type, confidence, doc_bbox = clf.predict(doc_path)
            self.assertEqual(doc_type, "id_card")
            self.assertGreaterEqual(confidence, DEFAULT_CONFIDENCE_THRESHOLD)
        finally:
            if os.path.exists(doc_path):
                os.remove(doc_path)

    def test_invalid_missing_image(self):
        """Verify missing image returns ('unknown', 0.0, None)."""
        clf = DocumentClassifier(device="cpu")
        doc_type, confidence, doc_bbox = clf.predict("nonexistent_path.jpg")
        self.assertEqual(doc_type, DEFAULT_CLASS)
        self.assertEqual(confidence, 0.0)
        self.assertIsNone(doc_bbox)


if __name__ == "__main__":
    unittest.main()
