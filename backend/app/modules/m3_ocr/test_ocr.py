"""
M3 OCR & Field Extraction Unit Tests (Tasks 3.2 & 3.3)
======================================================
Tests:
1. PaddleOCR component initialization.
2. Passport field extraction (real PaddleOCR).
3. ID card field extraction (real PaddleOCR).
4. Visa field extraction (real PaddleOCR).
5. Imperfect / partial document extraction demonstrating safe failure.
6. Visually adjacent merged text (verifying NO guessing: field='', conf=0.0).
7. Missing / corrupt / blank image handling.
8. Direct unit tests on FieldExtractor layout rules and confidence propagation.

Owner: P2
"""

import os
import tempfile
import unittest
from typing import List
from PIL import Image, ImageDraw

from backend.app.modules.m3_ocr.extractor import FieldExtractor
from backend.app.modules.m3_ocr.handler import run
from backend.app.modules.m3_ocr.ocr import (
    REQUIRED_FIELDS,
    SUPPORTED_DOC_TYPES,
    DocumentOCR,
)
from backend.app.schemas.contracts import (
    ClassifierOutput,
    IngestionOutput,
    OCROutput,
)


class TestM3FieldExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize OCR engine once to avoid repeated model loading
        cls.ocr_engine = DocumentOCR()
        cls.extractor = FieldExtractor()

    def _create_doc_image(self, lines: List[str], width: int = 650, height: int = 300) -> str:
        """Helper to create a temporary test image with clean text lines."""
        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        y = 20
        for text in lines:
            draw.text((25, y), text, fill=(0, 0, 0))
            y += 35
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        img.save(tmp.name)
        tmp.close()
        return tmp.name

    def _create_blank_image(self) -> str:
        """Helper to create a temporary blank image without text."""
        img = Image.new("RGB", (200, 100), color=(240, 240, 240))
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        img.save(tmp.name)
        tmp.close()
        return tmp.name

    def _create_corrupt_file(self) -> str:
        """Helper to create a temporary non-image corrupted file."""
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(b"CORRUPTED_NON_IMAGE_BINARY_DATA")
        tmp.close()
        return tmp.name

    # -------------------------------------------------------------------------
    # Initialization & Contract Safety Tests
    # -------------------------------------------------------------------------

    def test_ocr_component_initialization(self):
        """Verify DocumentOCR component initializes and has PaddleOCR engine."""
        self.assertIsNotNone(self.ocr_engine.ocr)
        self.assertIsNotNone(self.ocr_engine.extractor)
        self.assertEqual(self.ocr_engine.supported_doc_types, SUPPORTED_DOC_TYPES)
        self.assertEqual(self.ocr_engine.required_fields, REQUIRED_FIELDS)

    def test_empty_blank_image_safe_behavior(self):
        """Verify blank image returns empty fields and zero confidences."""
        blank_path = self._create_blank_image()
        try:
            result = run(blank_path, "visa")
            self.assertIsInstance(result, OCROutput)
            self.assertEqual(result.raw_text, "")
            self.assertEqual(len(result.fields), 6)
            for f in REQUIRED_FIELDS:
                self.assertEqual(result.fields[f], "")
                self.assertEqual(result.field_confidences[f], 0.0)
        finally:
            if os.path.exists(blank_path):
                os.remove(blank_path)

    def test_corrupt_unreadable_image_safe_behavior(self):
        """Verify corrupted image returns empty fields and zero confidences."""
        corrupt_path = self._create_corrupt_file()
        try:
            result = run(corrupt_path, "unknown")
            self.assertIsInstance(result, OCROutput)
            self.assertEqual(result.raw_text, "")
            self.assertEqual(len(result.fields), 6)
            for f in REQUIRED_FIELDS:
                self.assertEqual(result.fields[f], "")
                self.assertEqual(result.field_confidences[f], 0.0)
        finally:
            if os.path.exists(corrupt_path):
                os.remove(corrupt_path)

    def test_missing_nonexistent_image_safe_behavior(self):
        """Verify nonexistent image path returns empty fields safely."""
        result = run("nonexistent_file_xyz_123.png", "passport")
        self.assertIsInstance(result, OCROutput)
        self.assertEqual(result.raw_text, "")
        for f in REQUIRED_FIELDS:
            self.assertEqual(result.fields[f], "")
            self.assertEqual(result.field_confidences[f], 0.0)

    # -------------------------------------------------------------------------
    # Real PaddleOCR End-to-End Extraction Tests
    # -------------------------------------------------------------------------

    def test_passport_extraction_success(self):
        """Test A: Passport document field extraction and confidence mapping."""
        lines = [
            "PASSPORT",
            "PASSPORT NO: X8912345",
            "SURNAME: DOE",
            "GIVEN NAMES: JANE",
            "NATIONALITY: UTO",
            "DATE OF BIRTH: 15/05/1990",
            "DATE OF ISSUE: 10/01/2020",
            "DATE OF EXPIRY: 10/01/2030",
        ]
        img_path = self._create_doc_image(lines, height=320)
        try:
            result = run(img_path, "passport")
            self.assertIsInstance(result, OCROutput)

            # Check extracted fields
            self.assertIn("DOE", result.fields["name"])
            self.assertEqual(result.fields["doc_number"], "X8912345")
            self.assertEqual(result.fields["nationality"], "UTO")
            self.assertEqual(result.fields["dob"], "15/05/1990")
            self.assertEqual(result.fields["issue_date"], "10/01/2020")
            self.assertEqual(result.fields["expiry_date"], "10/01/2030")

            # Check confidences correspond to PaddleOCR rec_scores (> 0.8)
            for f in REQUIRED_FIELDS:
                self.assertGreater(result.field_confidences[f], 0.8)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def test_id_card_extraction_success(self):
        """Test B: ID card document field extraction and confidence mapping."""
        lines = [
            "NATIONAL IDENTITY CARD",
            "ID NO: ID-98765432",
            "FULL NAME: ALEX SMITH",
            "CITIZENSHIP: CAN",
            "DOB: 24/11/1985",
            "VALID FROM: 01/06/2018",
            "VALID THRU: 01/06/2028",
        ]
        img_path = self._create_doc_image(lines, height=290)
        try:
            result = run(img_path, "id_card")
            self.assertIsInstance(result, OCROutput)

            self.assertEqual(result.fields["name"], "ALEX SMITH")
            self.assertEqual(result.fields["doc_number"], "ID-98765432")
            self.assertEqual(result.fields["nationality"], "CAN")
            self.assertEqual(result.fields["dob"], "24/11/1985")
            self.assertEqual(result.fields["issue_date"], "01/06/2018")
            self.assertEqual(result.fields["expiry_date"], "01/06/2028")

            for f in REQUIRED_FIELDS:
                self.assertGreater(result.field_confidences[f], 0.8)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def test_visa_extraction_success(self):
        """Test C: Visa document field extraction and confidence mapping."""
        lines = [
            "VISA",
            "VISA NUMBER: V1234567",
            "BEARER: CARLOS SILVA",
            "NATIONALITY: BRA",
            "DATE OF BIRTH: 03/08/1992",
            "VALID FROM: 12/03/2023",
            "VALID UNTIL: 12/03/2024",
        ]
        img_path = self._create_doc_image(lines, height=290)
        try:
            result = run(img_path, "visa")
            self.assertIsInstance(result, OCROutput)

            self.assertEqual(result.fields["name"], "CARLOS SILVA")
            self.assertEqual(result.fields["doc_number"], "V1234567")
            self.assertEqual(result.fields["nationality"], "BRA")
            self.assertEqual(result.fields["dob"], "03/08/1992")
            self.assertEqual(result.fields["issue_date"], "12/03/2023")
            self.assertEqual(result.fields["expiry_date"], "12/03/2024")

            for f in REQUIRED_FIELDS:
                self.assertGreater(result.field_confidences[f], 0.8)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def test_imperfect_partial_extraction_safe_failure(self):
        """Test D: Imperfect document demonstrating safe failure on unextractable fields."""
        lines = [
            "TRAVEL DOCUMENT",
            "PASSPORT NO: P7766554",
            "NATIONALITY: UTO",
            "ILLEGIBLE / UNREADABLE SECTION #$%",
        ]
        img_path = self._create_doc_image(lines, height=200)
        try:
            result = run(img_path, "passport")
            self.assertIsInstance(result, OCROutput)

            # Extracted fields
            self.assertEqual(result.fields["doc_number"], "P7766554")
            self.assertGreater(result.field_confidences["doc_number"], 0.8)
            self.assertEqual(result.fields["nationality"], "UTO")
            self.assertGreater(result.field_confidences["nationality"], 0.8)

            # Missing/unextractable fields must be empty with 0.0 confidence
            self.assertEqual(result.fields["name"], "")
            self.assertEqual(result.field_confidences["name"], 0.0)
            self.assertEqual(result.fields["dob"], "")
            self.assertEqual(result.field_confidences["dob"], 0.0)
            self.assertEqual(result.fields["issue_date"], "")
            self.assertEqual(result.field_confidences["issue_date"], 0.0)
            self.assertEqual(result.fields["expiry_date"], "")
            self.assertEqual(result.field_confidences["expiry_date"], 0.0)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def test_visually_adjacent_merged_ambiguous_no_guessing(self):
        """
        Test E: Visually adjacent fields merged by OCR into a fused token (DOEGIVEN).
        Verifies that the extractor does NOT guess and returns '' with 0.0 confidence.
        """
        lines = [
            "PASSPORT",
            "PASSPORT NO: X1122334",
            "SURNAME: DOEGIVEN NAMES JANE",
            "DATE OF BIRTH: 12/08/1995",
            "DATE OF EXPIRY: 12/08/2035",
        ]
        img_path = self._create_doc_image(lines, height=220)
        try:
            result = run(img_path, "passport")
            self.assertIsInstance(result, OCROutput)

            # name boundary is ambiguous due to fused 'DOEGIVEN' -> must NOT guess
            self.assertEqual(result.fields["name"], "")
            self.assertEqual(result.field_confidences["name"], 0.0)

            # Other unambiguous fields remain correctly extracted
            self.assertEqual(result.fields["doc_number"], "X1122334")
            self.assertEqual(result.fields["dob"], "12/08/1995")
            self.assertEqual(result.fields["expiry_date"], "12/08/2035")
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    # -------------------------------------------------------------------------
    # Direct FieldExtractor Unit Tests (Layout & Rule Coverage)
    # -------------------------------------------------------------------------

    def test_extractor_unknown_conservative(self):
        """Verify unknown document type is conservative and only matches explicit labels."""
        mock_regions = [
            {"text": "SOME RANDOM TEXT", "score": 0.95},
            {"text": "DOCUMENT NO: DOC-998877", "score": 0.92},
            {"text": "DATE OF BIRTH: 01/01/2000", "score": 0.91},
        ]
        fields, confidences = self.extractor.extract(mock_regions, "unknown")
        self.assertEqual(fields["doc_number"], "DOC-998877")
        self.assertEqual(confidences["doc_number"], 0.92)
        self.assertEqual(fields["dob"], "01/01/2000")
        self.assertEqual(confidences["dob"], 0.91)
        self.assertEqual(fields["name"], "")
        self.assertEqual(confidences["name"], 0.0)

    def test_extractor_fused_doc_number_ambiguity(self):
        """Verify fused doc_number (e.g. X8912345EXPIRY) without delimiter is rejected."""
        mock_regions = [
            {"text": "PASSPORT NO: X8912345EXPIRY 10/10/2030", "score": 0.95},
        ]
        fields, confidences = self.extractor.extract(mock_regions, "passport")
        # Fused number with keyword without space/delimiter -> ambiguous, rejected
        self.assertEqual(fields["doc_number"], "")
        self.assertEqual(confidences["doc_number"], 0.0)

    # -------------------------------------------------------------------------
    # Adversarial Tests
    # -------------------------------------------------------------------------

    def test_adversarial_1_fused_label_and_value_rejected(self):
        """
        Adversarial Test 1: Field label is merged directly with its own value:
        'NATIONALITYUTO' (no whitespace, colon, or separator).
        Proves the extractor does NOT guess an arbitrary substring after a keyword.
        Must safely reject: nationality='', conf=0.0.
        """
        lines = ["NATIONALITYUTO"]
        img_path = self._create_doc_image(lines, height=120)
        try:
            result = run(img_path, "passport")
            self.assertIsInstance(result, OCROutput)
            # Fused label-value without deterministic separator -> MUST reject
            self.assertEqual(result.fields["nationality"], "")
            self.assertEqual(result.field_confidences["nationality"], 0.0)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def test_adversarial_2_fused_adjacent_dates_no_label_rejected(self):
        """
        Adversarial Test 2: Two adjacent values merged with NO label and NO separator:
        '1505199010012030' (conceptually DOB 15/05/1990 and EXPIRY 10/01/2030).
        Proves the extractor does NOT guess a date-pattern boundary without deterministic evidence.
        Must safely reject: dob='', expiry_date='', conf=0.0.
        """
        lines = ["1505199010012030"]
        img_path = self._create_doc_image(lines, height=120)
        try:
            result = run(img_path, "passport")
            self.assertIsInstance(result, OCROutput)
            # No labels, no separators -> MUST NOT guess dates
            self.assertEqual(result.fields["dob"], "")
            self.assertEqual(result.field_confidences["dob"], 0.0)
            self.assertEqual(result.fields["expiry_date"], "")
            self.assertEqual(result.field_confidences["expiry_date"], 0.0)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    # -------------------------------------------------------------------------
    # Generalization Tests (Shared Mechanism Verification)
    # -------------------------------------------------------------------------

    def test_generalization_1_fused_surname_fullname_collision_rejected(self):
        """
        Generalization 1: Different label collision (not GIVEN):
        'SURNAME: SMITHFULLNAME JOHN' (FULLNAME fused to SMITH without separator).
        Proves the shared boundary engine catches any fused document label collision.
        Must safely reject: name='', conf=0.0.
        """
        lines = ["SURNAME: SMITHFULLNAME JOHN"]
        img_path = self._create_doc_image(lines, height=120)
        try:
            result = run(img_path, "passport")
            self.assertIsInstance(result, OCROutput)
            self.assertEqual(result.fields["name"], "")
            self.assertEqual(result.field_confidences["name"], 0.0)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def test_generalization_2_fused_6digit_8digit_dates_rejected(self):
        """
        Generalization 2: 6-digit + 8-digit fused dates with NO label/separator:
        '15059010012030'.
        Proves the universal label-anchor requirement applies regardless of digit count.
        Must safely reject: dob='', expiry_date='', conf=0.0.
        """
        lines = ["15059010012030"]
        img_path = self._create_doc_image(lines, height=120)
        try:
            result = run(img_path, "passport")
            self.assertIsInstance(result, OCROutput)
            self.assertEqual(result.fields["dob"], "")
            self.assertEqual(result.field_confidences["dob"], 0.0)
            self.assertEqual(result.fields["expiry_date"], "")
            self.assertEqual(result.field_confidences["expiry_date"], 0.0)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)

    def test_generalization_3_fused_doc_number_label_value_rejected(self):
        """
        Generalization 3: Fused label+value for a different field (doc_number):
        'DOCNOX8912345' (no space, colon, or delimiter).
        Proves the separator requirement [:;\\.\\s\\-\\|]+ applies to doc_number identically.
        Must safely reject: doc_number='', conf=0.0.
        """
        lines = ["DOCNOX8912345"]
        img_path = self._create_doc_image(lines, height=120)
        try:
            result = run(img_path, "passport")
            self.assertIsInstance(result, OCROutput)
            self.assertEqual(result.fields["doc_number"], "")
            self.assertEqual(result.field_confidences["doc_number"], 0.0)
        finally:
            if os.path.exists(img_path):
                os.remove(img_path)


if __name__ == "__main__":
    unittest.main()
