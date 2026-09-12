"""
M6 — Tamper Heuristic: copy_move.py
=====================================
ORB-based copy-move (clone) detection.

Detects ORB keypoints, excludes those falling inside text regions
(because repeated printed characters are inherently self-similar and
would create false positives), self-matches the remaining descriptors,
and clusters match pairs by displacement vector to find evidence of
a contiguous patch being duplicated elsewhere in the image.

Owner: P3

Calibration note:
  nfeatures, hamming_threshold, min_pixel_dist, bucket_size,
  min_cluster_size, compactness_fraction, and score_divisor are
  initial heuristics.  They MUST be tuned against real specimen /
  tampered documents before the demo.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from typing import Dict, List, Tuple

import cv2
import numpy as np

from backend.app.modules.m6_tamper.text_mask import build_text_mask

logger = logging.getLogger(__name__)

# ─── Tunable constants ───────────────────────────
_N_FEATURES = 2500           # ORB keypoints to detect
_HAMMING_THRESHOLD = 32      # max Hamming distance for a valid match
_MIN_PIXEL_DIST = 24         # min Euclidean distance between matched pts
_BUCKET_SIZE = 8             # displacement-vector quantisation (pixels)
_MIN_CLUSTER_SIZE = 5        # min matches in a cluster to be meaningful
_COMPACTNESS_FRAC = 0.35     # max bounding-box diagonal as fraction of image diagonal
_SCORE_DIVISOR = 30.0        # normalise cluster size → [0, 1]
_MIN_NON_TEXT_KP = 20        # bail out if too few keypoints remain


def analyse(image_path: str) -> Tuple[float, List[List[int]]]:
    """
    Run ORB-based copy-move detection on the image at *image_path*.

    Returns
    -------
    (score, flagged_regions)
        score : float in [0, 1]  — higher = more suspicious
        flagged_regions : list of [x1, y1, x2, y2] bounding boxes

    On any failure returns (0.0, []).
    """
    try:
        return _analyse_impl(image_path)
    except Exception as exc:
        logger.warning("Copy-move detection failed for '%s': %s", image_path, exc)
        return 0.0, []


def _analyse_impl(image_path: str) -> Tuple[float, List[List[int]]]:
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        logger.warning("Could not load image for copy-move: %s", image_path)
        return 0.0, []

    h, w = img.shape[:2]
    img_diag = math.sqrt(h * h + w * w)

    # ── Detect ORB keypoints ──
    orb = cv2.ORB_create(nfeatures=_N_FEATURES)
    keypoints, descriptors = orb.detectAndCompute(img, None)

    if descriptors is None or len(keypoints) < _MIN_NON_TEXT_KP:
        return 0.0, []

    # ── Build text mask and exclude text keypoints ──
    text_mask = build_text_mask(img, dilate_px=4)
    non_text_indices = [
        i for i, kp in enumerate(keypoints)
        if not text_mask[int(kp.pt[1]), int(kp.pt[0])]
    ]

    if len(non_text_indices) < _MIN_NON_TEXT_KP:
        return 0.0, []

    filtered_kp = [keypoints[i] for i in non_text_indices]
    filtered_desc = descriptors[non_text_indices]

    # ── Self-match (k=3: idx-0 is always self at dist 0) ──
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    k = min(3, len(filtered_desc))
    if k < 2:
        return 0.0, []
    matches = bf.knnMatch(filtered_desc, filtered_desc, k=k)

    # ── Collect valid match pairs ──
    # Each match pair is (idx_a, idx_b, pt_a, pt_b, dx, dy)
    MatchPair = Tuple[int, int, Tuple[float, float], Tuple[float, float], float, float]
    valid_pairs: List[MatchPair] = []

    for i, match_group in enumerate(matches):
        pt_a = filtered_kp[i].pt
        for m in match_group:
            j = m.trainIdx
            if j == i:
                continue  # skip self-match
            if m.distance > _HAMMING_THRESHOLD:
                continue
            pt_b = filtered_kp[j].pt
            dx = pt_b[0] - pt_a[0]
            dy = pt_b[1] - pt_a[1]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < _MIN_PIXEL_DIST:
                continue
            valid_pairs.append((i, j, pt_a, pt_b, dx, dy))

    if not valid_pairs:
        return 0.0, []

    # ── Cluster by rounded displacement vector ──
    buckets: Dict[Tuple[int, int], List[MatchPair]] = defaultdict(list)
    for pair in valid_pairs:
        _, _, _, _, dx, dy = pair
        key = (round(dx / _BUCKET_SIZE), round(dy / _BUCKET_SIZE))
        buckets[key].append(pair)

    # ── Evaluate each bucket ──
    best_score = 0.0
    best_cluster: List[MatchPair] = []

    for key, cluster in buckets.items():
        if len(cluster) < _MIN_CLUSTER_SIZE:
            continue

        # Spatial compactness check — source points and dest points should
        # each be concentrated, not scattered all over the image.
        src_pts = np.array([(p[2][0], p[2][1]) for p in cluster])
        dst_pts = np.array([(p[3][0], p[3][1]) for p in cluster])

        src_diag = _bbox_diagonal(src_pts)
        dst_diag = _bbox_diagonal(dst_pts)

        if src_diag > _COMPACTNESS_FRAC * img_diag:
            continue
        if dst_diag > _COMPACTNESS_FRAC * img_diag:
            continue

        cluster_score = len(cluster) / _SCORE_DIVISOR
        if cluster_score > best_score:
            best_score = cluster_score
            best_cluster = cluster

    score = round(min(max(best_score, 0.0), 1.0), 4)

    # ── Build flagged regions from matched pairs ──
    flagged: List[List[int]] = []
    if best_cluster:
        src_pts = np.array([(p[2][0], p[2][1]) for p in best_cluster])
        dst_pts = np.array([(p[3][0], p[3][1]) for p in best_cluster])

        src_box = _bbox_from_points(src_pts)
        dst_box = _bbox_from_points(dst_pts)

        if src_box:
            flagged.append(src_box)
        if dst_box:
            flagged.append(dst_box)

    return score, flagged


def _bbox_diagonal(pts: np.ndarray) -> float:
    """Compute the diagonal of the axis-aligned bounding box of *pts*."""
    if len(pts) == 0:
        return 0.0
    mins = pts.min(axis=0)
    maxs = pts.max(axis=0)
    dx = maxs[0] - mins[0]
    dy = maxs[1] - mins[1]
    return math.sqrt(dx * dx + dy * dy)


def _bbox_from_points(pts: np.ndarray) -> List[int] | None:
    """Return [x1, y1, x2, y2] bounding box enclosing all *pts*, or None."""
    if len(pts) == 0:
        return None
    x1 = int(pts[:, 0].min())
    y1 = int(pts[:, 1].min())
    x2 = int(pts[:, 0].max())
    y2 = int(pts[:, 1].max())
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]
