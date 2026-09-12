import os
import uuid
import shutil
import unittest
import numpy as np
import cv2

from backend.app.modules.m1_ingestion import run
from backend.app.schemas.contracts import IngestionOutput

class TestM1Ingestion(unittest.TestCase):
    
    def generate_synthetic_image_bytes(self) -> bytes:
        # Create a white background
        img = np.ones((200, 300, 3), dtype=np.uint8) * 255
        
        # Draw a black rectangle (like a document) somewhat skewed
        points = np.array([[50, 50], [250, 80], [220, 180], [20, 150]], dtype=np.int32)
        cv2.fillPoly(img, [points], (0, 0, 0))
        
        # Encode to jpg bytes
        success, encoded_image = cv2.imencode('.jpg', img)
        self.assertTrue(success)
        return encoded_image.tobytes()
        
    def test_m1_ingestion_valid_preprocessing(self):
        doc_bytes = self.generate_synthetic_image_bytes()
        live_photo_bytes = b"dummy_live_photo_content"
        doc_hint = "passport"

        output = run(
            doc_image_bytes=doc_bytes,
            live_photo_bytes=live_photo_bytes,
            doc_type_hint=doc_hint
        )

        # 1. Verify a UUID session_id is generated
        self.assertTrue(hasattr(output, "session_id"))
        self.assertIsInstance(output.session_id, str)

        # 9. Verify returned object is IngestionOutput
        self.assertIsInstance(output, IngestionOutput)

        # 8. Verify doc_type_hint is preserved
        self.assertEqual(output.doc_type_hint, doc_hint)

        # 3. doc_image_path points to doc_preprocessed.jpg
        self.assertTrue(output.doc_image_path.endswith("doc_preprocessed.jpg"))
        
        # 4. live_photo_path still points to live_photo.jpg
        self.assertTrue(output.live_photo_path.endswith("live_photo.jpg"))

        # 2. doc_preprocessed.jpg is created
        self.assertTrue(os.path.exists(output.doc_image_path))
        
        # 5. The raw document still exists
        storage_dir = os.path.dirname(output.doc_image_path)
        doc_raw_path = os.path.join(storage_dir, "doc_raw.jpg")
        self.assertTrue(os.path.exists(doc_raw_path))

        # Check raw document content matches what was sent
        with open(doc_raw_path, "rb") as f:
            self.assertEqual(f.read(), doc_bytes)

        # 6. The live photo bytes remain unchanged
        self.assertTrue(os.path.exists(output.live_photo_path))
        with open(output.live_photo_path, "rb") as f:
            self.assertEqual(f.read(), live_photo_bytes)
            
        # IMPORTANT: verify preprocessed file is a decodable image
        preprocessed_img = cv2.imread(output.doc_image_path)
        self.assertIsNotNone(preprocessed_img)
        self.assertGreater(preprocessed_img.size, 0)

        # Cleanup
        if os.path.exists(storage_dir):
            shutil.rmtree(storage_dir)

    def test_m1_ingestion_corrupt_fallback(self):
        # 7. Corrupt/non-decodable document falls back to doc_raw.jpg
        doc_bytes = b"this is not a valid image format"
        live_photo_bytes = b"dummy_live_photo_content"
        doc_hint = "visa"

        output = run(
            doc_image_bytes=doc_bytes,
            live_photo_bytes=live_photo_bytes,
            doc_type_hint=doc_hint
        )

        # Fallback should happen, returning doc_raw.jpg
        self.assertTrue(output.doc_image_path.endswith("doc_raw.jpg"))
        
        # The raw file should exist and have the exact bytes
        self.assertTrue(os.path.exists(output.doc_image_path))
        with open(output.doc_image_path, "rb") as f:
            self.assertEqual(f.read(), doc_bytes)
            
        # Check preprocessed file does NOT exist
        storage_dir = os.path.dirname(output.doc_image_path)
        doc_preprocessed_path = os.path.join(storage_dir, "doc_preprocessed.jpg")
        self.assertFalse(os.path.exists(doc_preprocessed_path))

        # Cleanup
        if os.path.exists(storage_dir):
            shutil.rmtree(storage_dir)

    def test_m1_ingestion_invalid_input(self):
        with self.assertRaises(TypeError):
            run(doc_image_bytes="not bytes", live_photo_bytes=b"bytes")
            
        with self.assertRaises(TypeError):
            run(doc_image_bytes=b"bytes", live_photo_bytes="not bytes")

if __name__ == "__main__":
    unittest.main()
