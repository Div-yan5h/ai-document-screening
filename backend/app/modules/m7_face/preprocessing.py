"""
M7 — Face Verification Preprocessing
====================================
Image loading, validation, and deterministic face candidate selection utilities.
Keeps image handling decoupled from the InsightFace model lifecycle.

Owner: P4 (Identity & Records)
"""

import os
from typing import Any, Optional, Sequence

import cv2
import numpy as np


def calculate_bbox_area(bbox: Optional[Sequence[float]]) -> float:
    """
    Calculate the area of a bounding box [x1, y1, x2, y2].

    Formula:
        max(0.0, x2 - x1) * max(0.0, y2 - y1)

    Guarantees:
        - Inverted coordinates (x2 < x1 or y2 < y1) yield 0.0.
        - Non-numeric or incomplete boxes yield 0.0.
        - Negative dimensions never produce a positive area.
    """
    if bbox is None or len(bbox) < 4:
        return 0.0

    try:
        x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        width = max(0.0, x2 - x1)
        height = max(0.0, y2 - y1)
        return width * height
    except (TypeError, ValueError, IndexError):
        return 0.0


def extract_bbox(candidate: Any) -> Optional[Sequence[float]]:
    """
    Extract a 4-element bounding box [x1, y1, x2, y2] from various candidate formats:
    - Object with .bbox attribute (InsightFace Face object)
    - Dictionary with 'bbox' key
    - Sequence / numpy array of at least 4 coordinates
    """
    if candidate is None:
        return None

    if hasattr(candidate, "bbox"):
        return candidate.bbox

    if isinstance(candidate, dict) and "bbox" in candidate:
        return candidate["bbox"]

    if isinstance(candidate, (list, tuple, np.ndarray)) and len(candidate) >= 4:
        return candidate

    return None


def select_primary_face(faces: Optional[Sequence[Any]]) -> Optional[Any]:
    """
    Deterministically select the primary face from detected face candidates.

    Policy:
        - 0 faces (or None / empty) -> return None
        - 1 face -> return that face
        - multiple faces -> return candidate with largest bounding-box area

    Stability:
        In case of identical areas, preserves the first encountered candidate.

    Args:
        faces: Sequence of detected face candidate objects/dictionaries.

    Returns:
        Selected primary face candidate, or None if no faces provided.
    """
    if not faces:
        return None

    if len(faces) == 1:
        return faces[0]

    return max(
        faces,
        key=lambda face: calculate_bbox_area(extract_bbox(face)),
    )


def validate_image(image: Any, source_path: Optional[str] = None) -> None:
    """
    Validate that an in-memory image array is non-empty and well-formed.

    Args:
        image: Array to validate.
        source_path: Optional path for error context.

    Raises:
        ValueError: If image is None, empty, or not a valid 2D/3D image array.
    """
    context = f" from '{source_path}'" if source_path else ""

    if image is None:
        raise ValueError(
            f"Failed to load image{context}: cv2.imread returned None (unreadable or corrupt format)."
        )

    if not isinstance(image, np.ndarray):
        raise ValueError(
            f"Invalid image type{context}: expected numpy.ndarray, got {type(image).__name__}."
        )

    if image.size == 0 or image.ndim not in (2, 3):
        shape_info = getattr(image, "shape", None)
        raise ValueError(f"Invalid image dimensions{context}: shape={shape_info}.")

    if image.shape[0] <= 0 or image.shape[1] <= 0:
        raise ValueError(
            f"Invalid image resolution{context}: height={image.shape[0]}, width={image.shape[1]}."
        )


def load_image(image_path: str) -> np.ndarray:
    """
    Load an image from a filesystem path in BGR format and validate integrity.

    Args:
        image_path: Path to the image file.

    Returns:
        np.ndarray containing decoded BGR image.

    Raises:
        ValueError: If the path is empty, file does not exist, or image cannot be decoded.
    """
    if not image_path or not isinstance(image_path, str):
        raise ValueError(f"Invalid image path provided: {image_path!r}")

    if not os.path.isfile(image_path):
        raise ValueError(f"Image file not found: {image_path!r}")

    image = cv2.imread(image_path)
    validate_image(image, source_path=image_path)
    return image
