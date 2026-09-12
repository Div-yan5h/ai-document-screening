"""
M6 — Tamper Heuristic: ela.py
===============================
Error Level Analysis (ELA).

Re-saves the image at a fixed JPEG quality, diffs against the original,
and uses the error map to detect regions with suspicious compression
artefact inconsistencies.

Owner: P3

Calibration note:
  The JPEG quality (90), threshold percentile (98th), coverage/severity
  weighting, and morphological kernel sizes below are initial heuristics.
  They MUST be tuned against real specimen / tampered documents before the
  demo — do not treat them as production-ready.
"""

from __future__ import annotations

import io
import logging
from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image, ImageChops

logger = logging.getLogger(__name__)

# ─── Tunable constants ───────────────────────────
_JPEG_QUALITY = 90          # quality for the re-save pass
_PERCENTILE_THRESHOLD = 98  # top-N% error pixels are "outliers"
_SEVERITY_DIVISOR = 80.0    # normalises mean-outlier-intensity → [0,1]
_COVERAGE_WEIGHT = 0.6      # blend weight for coverage component
_SEVERITY_WEIGHT = 0.4      # blend weight for severity component
_MORPH_KERNEL = (7, 7)      # close kernel to merge nearby error pixels


def analyse(image_path: str) -> Tuple[float, List[List[int]]]:
    """
    Run Error Level Analysis on the image at *image_path*.

    Returns
    -------
    (score, flagged_regions)
        score : float in [0, 1]  — higher = more suspicious
        flagged_regions : list of [x1, y1, x2, y2] bounding boxes
                          around high-error clusters

    On any failure (bad path, unreadable image, OpenCV error, etc.)
    returns (0.0, []).
    """
    try:
        return _analyse_impl(image_path)
    except Exception as exc:
        logger.warning("ELA failed for '%s': %s", image_path, exc)
        return 0.0, []


def _analyse_impl(image_path: str) -> Tuple[float, List[List[int]]]:
    # ── Load original ──
    original = Image.open(image_path).convert("RGB")

    # ── Re-save at fixed JPEG quality into memory ──
    buf = io.BytesIO()
    original.save(buf, format="JPEG", quality=_JPEG_QUALITY)
    buf.seek(0)
    resaved = Image.open(buf).convert("RGB")

    # ── Per-pixel absolute difference ──
    diff = ImageChops.difference(original, resaved)

    # Convert to numpy for analysis
    diff_arr = np.array(diff, dtype=np.float64)  # (H, W, 3)

    # Per-pixel max-channel error
    error_map = diff_arr.max(axis=2)  # (H, W)

    if error_map.max() == 0:
        # Identical images (e.g. already a JPEG at that quality) — no suspicion
        return 0.0, []

    # ── Threshold at the high percentile ──
    threshold = float(np.percentile(error_map, _PERCENTILE_THRESHOLD))
    if threshold < 1.0:
        threshold = 1.0  # avoid degenerate all-zero mask

    outlier_mask = (error_map >= threshold).astype(np.uint8) * 255

    # Coverage = fraction of pixels that are outliers
    total_pixels = error_map.shape[0] * error_map.shape[1]
    outlier_count = int(np.count_nonzero(outlier_mask))
    coverage = outlier_count / total_pixels

    # Severity = mean intensity of outlier pixels, normalised
    outlier_values = error_map[error_map >= threshold]
    severity = float(outlier_values.mean()) / _SEVERITY_DIVISOR if len(outlier_values) > 0 else 0.0

    score = coverage * _COVERAGE_WEIGHT + severity * _SEVERITY_WEIGHT
    score = round(min(max(score, 0.0), 1.0), 4)

    # ── Bounding boxes via contours ──
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, _MORPH_KERNEL)
    closed = cv2.morphologyEx(outlier_mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    flagged: List[List[int]] = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Skip tiny noise blobs
        if w < 4 or h < 4:
            continue
        flagged.append([x, y, x + w, y + h])

    return score, flagged
