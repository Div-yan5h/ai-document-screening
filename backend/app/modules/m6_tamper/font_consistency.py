"""
M6 — Tamper Heuristic: font_consistency.py
============================================
Character-height consistency signal.

Detects candidate character glyphs, groups them into horizontal text lines,
and evaluates both intra-line (within-line) height variance and inter-line
(rogue font size) anomalies.

Why line-level analysis is required:
  In genuine documents (passports, national ID cards, voter cards), different
  text lines legitimately use different font sizes (e.g., document title in 24px,
  body fields in 14px).  A global variance check across the entire document
  inevitably flags genuine documents as having high variance (>0.90).
  Moreover, non-text visual features (emblems, photos, stamps, borders)
  create arbitrary connected components that further corrupt global statistics.

Filtering & Detection Pipeline:
  1. Otsu thresholding (inverted) to isolate dark ink on light background.
  2. Connected components analysis with multi-stage geometric filtering:
     - Height bounds: ignores noise specks (< 7px) and large logos (> 60px).
     - Aspect ratio bounds: ignores horizontal rules and vertical margin borders.
     - Area & extent bounds: ignores sparse boundary noise and hollow artifacts.
  3. Text line grouping:
     - Clusters glyphs sharing vertical alignment (y-center overlap).
     - Splits segments across large horizontal gaps (> 3.5x line height) to separate
       isolated seals/columns from actual text lines.
     - Retains valid lines with at least 3 characters (isolates non-text noise).
  4. Scoring:
     - Intra-line consistency: measures within-line coefficient of variation (CV).
     - Inter-line anomaly: checks for small rogue text blocks (< 10 glyphs) with
       heights deviating sharply from the document's body text median.
     - Outlier flagging: flags glyphs deviating > 2 sigma from their line mean.

Owner: P3
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ─── Tunable Calibration Constants ────────────────
_MIN_GLYPH_REGIONS = 8          # minimum total glyphs across document to evaluate
_MIN_GLYPH_HEIGHT = 7           # absolute minimum height (px) for a character
_MAX_GLYPH_HEIGHT_FRAC = 0.10   # maximum height as fraction of image height (cap ~60px)
_MIN_AREA = 16                  # minimum pixel area for a character glyph
_MAX_AREA_FRAC = 0.015          # maximum area fraction of document (~1.5%)
_MIN_ASPECT = 0.12              # min aspect ratio (w/h) — rejects vertical margin lines
_MAX_ASPECT = 4.5               # max aspect ratio (w/h) — rejects horizontal rules
_MIN_EXTENT = 0.12              # min solidity/extent (area / (w*h)) — rejects hollow noise
_MAX_EXTENT = 1.0               # max extent (allows solid characters / rectangular test fonts)

# Line clustering & scoring parameters
_LINE_OVERLAP_FACTOR = 0.55     # fraction of glyph height for vertical line clustering
_LINE_GAP_FACTOR = 3.5          # max horizontal space factor before splitting lines
_MIN_LINE_GLYPHS = 3            # minimum characters to form a valid text line
_OUTLIER_SIGMA = 2.0            # within-line standard deviation threshold for outlier flagging
_OUTLIER_REL_DIFF = 0.45        # relative height difference threshold from line mean (45%)

# Baseline tolerances for genuine multi-line / multi-script documents
_BASELINE_INTRA_CV = 0.10       # expected normal natural font variance within a line
_INTRA_CV_DIVISOR = 0.20        # divisor for excess intra-line variance
_MAX_LINE_CV_TOLERANCE = 0.25   # max single-line CV tolerated before penalty
_MAX_LINE_CV_DIVISOR = 0.25     # divisor for max single-line CV spike
_ROGUE_RATIO_THRESHOLD = 0.45   # font height difference ratio to flag an isolated rogue line


def analyse(
    image_path: str,
    raw_text: str = "",
) -> Tuple[float, List[List[int]]]:
    """
    Measure character-height consistency across document text lines.

    Parameters
    ----------
    image_path : str
        Path to the (preprocessed) document image.
    raw_text : str
        M3 OCR raw text. Accepted for interface symmetry; statistics
        are derived from spatial character geometry in the image.

    Returns
    -------
    (score, flagged_regions)
        score : float in [0, 1] — higher = more inconsistent / suspicious
        flagged_regions : list of [x1, y1, x2, y2] for outlier glyphs

    On any failure or insufficient data returns (0.0, []).
    """
    try:
        return _analyse_impl(image_path)
    except Exception as exc:
        logger.warning("Font-consistency analysis failed for '%s': %s", image_path, exc)
        return 0.0, []


# Alias for explicit naming
compute_font_inconsistency = analyse


def _extract_candidate_glyphs(img: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """
    Extract candidate character bounding boxes using inverted Otsu binarization
    and morphological geometric filtering to discard non-character elements.
    """
    h, w = img.shape[:2]
    total_area = h * w
    min_h = max(int(h * 0.012), _MIN_GLYPH_HEIGHT)
    max_h = min(max(int(h * _MAX_GLYPH_HEIGHT_FRAC), 45), 65)
    max_area = int(total_area * _MAX_AREA_FRAC)

    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    glyphs: List[Tuple[int, int, int, int]] = []
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        gx = stats[i, cv2.CC_STAT_LEFT]
        gy = stats[i, cv2.CC_STAT_TOP]
        gw = stats[i, cv2.CC_STAT_WIDTH]
        gh = stats[i, cv2.CC_STAT_HEIGHT]

        # Height filtering (ignores tiny noise specks and huge photo blocks)
        if gh < min_h or gh > max_h:
            continue

        # Aspect ratio filtering (ignores horizontal rules and vertical border lines)
        aspect = gw / gh if gh > 0 else 0.0
        if aspect < _MIN_ASPECT or aspect > _MAX_ASPECT:
            continue

        # Area and extent filtering (ignores sparse outlines and background texture)
        if area < _MIN_AREA or area > max_area:
            continue
        extent = area / (gw * gh) if (gw * gh) > 0 else 0.0
        if extent < _MIN_EXTENT or extent > _MAX_EXTENT:
            continue

        glyphs.append((int(gx), int(gy), int(gw), int(gh)))

    return glyphs


def _group_glyphs_into_lines(
    glyphs: List[Tuple[int, int, int, int]],
) -> List[List[Tuple[int, int, int, int]]]:
    """
    Group candidate glyphs into horizontal text lines based on vertical overlap
    and horizontal proximity.

    Separates columns and isolated seals from centered or adjacent text lines.
    """
    if not glyphs:
        return []

    # Sort primarily by vertical center, secondarily by x
    sorted_glyphs = sorted(glyphs, key=lambda g: (g[1] + g[3] / 2.0, g[0]))

    # Step 1: Cluster into vertical y-bands
    y_bands: List[List[Tuple[int, int, int, int]]] = []
    for g in sorted_glyphs:
        gx, gy, gw, gh = g
        g_cy = gy + gh / 2.0
        matched = False

        for band in y_bands:
            med_h = float(np.median([item[3] for item in band]))
            med_cy = float(np.median([item[1] + item[3] / 2.0 for item in band]))

            if abs(g_cy - med_cy) < max(med_h, gh) * _LINE_OVERLAP_FACTOR:
                band.append(g)
                matched = True
                break

        if not matched:
            y_bands.append([g])

    # Step 2: Within each y-band, sort left-to-right and split on large horizontal gaps
    lines: List[List[Tuple[int, int, int, int]]] = []
    for band in y_bands:
        band.sort(key=lambda g: g[0])
        curr_segment = [band[0]]

        for g in band[1:]:
            prev_x2 = curr_segment[-1][0] + curr_segment[-1][2]
            curr_x1 = g[0]
            gap = curr_x1 - prev_x2
            seg_h = float(np.median([item[3] for item in curr_segment]))
            max_allowed_gap = max(seg_h * _LINE_GAP_FACTOR, 60.0)

            if gap <= max_allowed_gap:
                curr_segment.append(g)
            else:
                lines.append(curr_segment)
                curr_segment = [g]

        lines.append(curr_segment)

    return lines


def _analyse_impl(image_path: str) -> Tuple[float, List[List[int]]]:
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        logger.warning("Could not load image for font consistency: %s", image_path)
        return 0.0, []

    h, w = img.shape[:2]
    glyphs = _extract_candidate_glyphs(img)

    if len(glyphs) < _MIN_GLYPH_REGIONS:
        return 0.0, []

    lines = _group_glyphs_into_lines(glyphs)
    valid_lines = [l for l in lines if len(l) >= _MIN_LINE_GLYPHS]

    total_line_glyphs = sum(len(l) for l in valid_lines)
    if not valid_lines or total_line_glyphs < _MIN_GLYPH_REGIONS:
        return 0.0, []

    flagged_boxes: List[List[int]] = []
    line_cvs: List[float] = []
    line_weights: List[int] = []
    line_means: List[float] = []
    line_spans: List[int] = []

    # ── Evaluate Intra-line (Within-line) Variance ──
    for l in valid_lines:
        hs = np.array([g[3] for g in l], dtype=np.float64)
        m = float(hs.mean())
        s = float(hs.std())
        cv_val = s / m if m > 0 else 0.0

        line_cvs.append(cv_val)
        line_weights.append(len(l))
        line_means.append(m)

        xs = [g[0] for g in l]
        x_maxs = [g[0] + g[2] for g in l]
        line_spans.append(max(x_maxs) - min(xs))

        # Flag outlier glyphs within this specific line
        for (gx, gy, gw, gh) in l:
            if s > 2.0 and abs(gh - m) > _OUTLIER_SIGMA * s:
                flagged_boxes.append([int(gx), int(gy), int(gx + gw), int(gy + gh)])
            elif abs(gh - m) / m > _OUTLIER_REL_DIFF:
                flagged_boxes.append([int(gx), int(gy), int(gx + gw), int(gy + gh)])

    # ── Evaluate Inter-line (Rogue Font Size Block) Anomaly ──
    # Compute the median character height representing the document body text
    all_heights = [g[3] for l in valid_lines for g in l]
    doc_median_h = float(np.median(all_heights))

    inter_line_penalty = 0.0
    for idx, l in enumerate(valid_lines):
        m = line_means[idx]
        count = len(l)
        span = line_spans[idx]
        ratio = abs(m - doc_median_h) / doc_median_h if doc_median_h > 0 else 0.0

        # A rogue spliced block is characterized by:
        #   - Sharp height difference from the body median (> 45%)
        #   - Isolated short span (< 30% of document width or < 10 characters)
        #   - Differs from legitimate full-width official header lines
        if ratio > _ROGUE_RATIO_THRESHOLD and (count < 10 or span < 0.30 * w):
            severity = min((ratio - 0.40) / 0.60, 1.0)
            inter_line_penalty = max(inter_line_penalty, severity)
            for (gx, gy, gw, gh) in l:
                box = [int(gx), int(gy), int(gx + gw), int(gy + gh)]
                if box not in flagged_boxes:
                    flagged_boxes.append(box)

    # ── Combine Signals into Normalized Suspicion Score ──
    weighted_intra_cv = float(np.average(line_cvs, weights=line_weights))
    max_intra_cv = float(np.max(line_cvs))

    # Genuine documents naturally have intra-line CV in [0.10, 0.20].
    # We penalize excess variance beyond expected baseline.
    excess_cv = max(weighted_intra_cv - _BASELINE_INTRA_CV, 0.0)
    excess_max = max(max_intra_cv - _MAX_LINE_CV_TOLERANCE, 0.0)

    raw_score = (
        (excess_cv / _INTRA_CV_DIVISOR) * 0.35 +
        (excess_max / _MAX_LINE_CV_DIVISOR) * 0.35 +
        inter_line_penalty * 0.40
    )

    score = round(min(max(raw_score, 0.0), 1.0), 4)

    return score, flagged_boxes
