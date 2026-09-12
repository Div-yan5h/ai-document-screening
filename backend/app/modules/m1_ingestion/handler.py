"""
M1 — Ingestion & Preprocessing
======================================
Implements baseline ingestion, storage logic, and OpenCV preprocessing.

Owner: P1
"""

import os
import uuid
import logging
from typing import Optional

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = None
    np = None

from backend.app.schemas.contracts import IngestionOutput

logger = logging.getLogger(__name__)

def preprocess_document(image_path: str, output_path: str) -> bool:
    """
    Applies OpenCV preprocessing pipeline to the image at image_path,
    and saves the result to output_path.
    Returns True if successful, False otherwise.
    """
    if cv2 is None or np is None:
        logger.error("OpenCV/NumPy is not installed. Skipping preprocessing.")
        return False
        
    try:
        # 1. Read the saved raw document with OpenCV
        img = cv2.imread(image_path)
        if img is None:
            logger.error(f"Failed to read image at {image_path}")
            return False
            
        # 2. Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 3. Deskew
        # Thresholding
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
        
        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            logger.warning("No contours found for deskewing.")
            deskewed = gray
        else:
            # Select the largest relevant contour
            largest_contour = max(contours, key=cv2.contourArea)
            
            # minAreaRect — compute skew angle directly from box geometry,
            # independent of OpenCV version's angle-sign convention
            rect = cv2.minAreaRect(largest_contour)
            box = cv2.boxPoints(rect)

            edge1 = box[1] - box[0]
            edge2 = box[2] - box[1]
            edge = edge1 if np.linalg.norm(edge1) > np.linalg.norm(edge2) else edge2

            angle = np.degrees(np.arctan2(edge[1], edge[0]))
            angle = angle % 90
            if angle > 45:
                angle -= 90
                
            # Rotate with cv2.warpAffine
            (h, w) = gray.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, angle, 1.0)
            deskewed = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
            
        # 4. Denoise
        denoised = cv2.fastNlMeansDenoising(deskewed, None, 10, 7, 21)
        
        # 5. Improve contrast using CLAHE
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrasted = clahe.apply(denoised)
        
        # 6. Save the result
        success = cv2.imwrite(output_path, contrasted)
        if not success:
            logger.error(f"Failed to write preprocessed image to {output_path}")
            return False
            
        return True
    except Exception as e:
        logger.error(f"Preprocessing failed with exception: {e}")
        return False

def run(
    doc_image_bytes: bytes,
    live_photo_bytes: bytes,
    doc_type_hint: Optional[str] = None
) -> IngestionOutput:
    """
    Ingests raw documents and live photos.
    Generates a session ID and saves the bytes to the session directory.
    Attempts to preprocess the document image.
    Falls back to raw image if preprocessing fails.
    """
    if not isinstance(doc_image_bytes, bytes):
        raise TypeError("doc_image_bytes must be bytes")
    if not isinstance(live_photo_bytes, bytes):
        raise TypeError("live_photo_bytes must be bytes")

    session_id = str(uuid.uuid4())
    
    # Anchor storage to the repository root instead of the current working directory
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
    storage_dir = os.path.join(repo_root, "storage", "sessions", session_id)
    os.makedirs(storage_dir, exist_ok=True)
    
    doc_raw_path = os.path.join(storage_dir, "doc_raw.jpg")
    live_photo_path = os.path.join(storage_dir, "live_photo.jpg")
    
    with open(doc_raw_path, "wb") as f:
        f.write(doc_image_bytes)
        
    with open(live_photo_path, "wb") as f:
        f.write(live_photo_bytes)
        
    # Attempt preprocessing
    doc_preprocessed_path = os.path.join(storage_dir, "doc_preprocessed.jpg")
    preprocessing_success = preprocess_document(doc_raw_path, doc_preprocessed_path)
    
    final_doc_path = doc_preprocessed_path if preprocessing_success else doc_raw_path
        
    return IngestionOutput(
        session_id=session_id,
        doc_image_path=final_doc_path,
        live_photo_path=live_photo_path,
        doc_type_hint=doc_type_hint,
    )
