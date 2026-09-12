"""
M6 — Tamper Heuristic: text_mask.py
====================================
Shared helper for detecting text-region bounding boxes via Otsu threshold
and morphological operations.  Used by copy_move.py (to exclude text
keypoints) and potentially by other signals.

Owner: P3
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


def detect_text_regions(gray: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """
    Detect candidate text-line bounding boxes in a grayscale image.

    Strategy:
      1. Otsu-threshold the grayscale image.
      2. MORPH_CLOSE with a wide horizontal kernel (15×5) to merge
         individual glyphs into word/line blobs.
      3. Find connected components.
      4. Keep only those whose height is roughly 6–15 % of the image
         height, filtering out noise specks and large non-text blobs.
      5. Exclude large, roughly-square blobs (width/height < ~1.3 and
         height > ~25 px) — those are photos, seals, or solid graphic
         blocks, not text.

    Returns a list of (x1, y1, x2, y2) bounding boxes.
    """
    if gray is None or gray.size == 0:
        return []

    h, w = gray.shape[:2]

    # Otsu threshold — invert so text (dark on light) becomes white
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    # Horizontal close to merge glyphs into word/line blobs
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

    # Find connected components
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)

    min_h = max(int(h * 0.015), 4)
    max_h = int(h * 0.20)

    regions: List[Tuple[int, int, int, int]] = []
    for i in range(1, num_labels):  # skip background label 0
        x = stats[i, cv2.CC_STAT_LEFT]
        y = stats[i, cv2.CC_STAT_TOP]
        cw = stats[i, cv2.CC_STAT_WIDTH]
        ch = stats[i, cv2.CC_STAT_HEIGHT]

        # Filter by height as a fraction of image height
        if ch < min_h or ch > max_h:
            continue

        # Exclude large, roughly-square blobs — photos, seals, logos
        # A text line is much wider than tall; a photo/seal is roughly square.
        aspect = cw / ch if ch > 0 else 0
        if aspect < 1.3 and ch > 25:
            continue

        regions.append((x, y, x + cw, y + ch))

    return regions


def build_text_mask(gray: np.ndarray, dilate_px: int = 4) -> np.ndarray:
    """
    Build a boolean mask where True = "this pixel is inside a text region."

    Uses detect_text_regions() and expands each box by *dilate_px* pixels
    on every side to provide a safety margin around detected text.

    Returns an ndarray of shape (H, W) with dtype bool.
    """
    h, w = gray.shape[:2]
    mask = np.zeros((h, w), dtype=bool)

    regions = detect_text_regions(gray)
    for (x1, y1, x2, y2) in regions:
        # Expand by dilate_px, clamped to image bounds
        rx1 = max(0, x1 - dilate_px)
        ry1 = max(0, y1 - dilate_px)
        rx2 = min(w, x2 + dilate_px)
        ry2 = min(h, y2 + dilate_px)
        mask[ry1:ry2, rx1:rx2] = True

    return mask
