"""
M6 — Tamper Heuristic: Calibration Tool
=======================================
Manual CLI tool to inspect individual signal scores and calibrate constants
against real specimen and tampered document images.

Usage:
    python calibration_tool.py <image_path> [<image_path> ...]

Example:
    python calibration_tool.py path/to/clean.jpg path/to/tampered.jpg
"""

from __future__ import annotations

import os
import sys
from typing import List

# Ensure backend root is available on sys.path
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.abspath(os.path.join(_current_dir, "..", "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from backend.app.modules.m6_tamper import ela, copy_move, font_consistency

# Function mappings
compute_ela = getattr(ela, "compute_ela", ela.analyse)
detect_copy_move = getattr(copy_move, "detect_copy_move", copy_move.analyse)
compute_font_inconsistency = getattr(font_consistency, "compute_font_inconsistency", font_consistency.analyse)


def evaluate_image(image_path: str):
    """Run all 3 signals on a single image and return detailed breakdown."""
    if not os.path.exists(image_path):
        print(f"[-] Error: File not found at '{image_path}'")
        return None

    ela_score, ela_regions = compute_ela(image_path)
    cm_score, cm_regions = detect_copy_move(image_path)
    font_score, font_regions = compute_font_inconsistency(image_path, raw_text="")

    suspicion_score = round((ela_score + cm_score + font_score) / 3, 4)

    return {
        "path": image_path,
        "ela": {
            "score": ela_score,
            "regions_count": len(ela_regions),
            "constants": "quality=90, percentile=98th, severity_div=80.0, weights=(0.6 cov / 0.4 sev)",
        },
        "copy_move": {
            "score": cm_score,
            "regions_count": len(cm_regions),
            "constants": "hamming_thresh=32, min_dist=24px, bucket=8px, min_cluster=5, max_diag=35%, score_div=30.0",
        },
        "font_consistency": {
            "score": font_score,
            "regions_count": len(font_regions),
            "constants": "cv_div=0.45, min_regions=8, deviation_sigma=2.0",
        },
        "suspicion_score": suspicion_score,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python calibration_tool.py <image_path> [<image_path> ...]")
        print("Provide one or more image paths to evaluate tamper heuristic signals.")
        sys.exit(1)

    image_paths = sys.argv[1:]
    results = []

    print("\n" + "=" * 76)
    print(" M6 TAMPER HEURISTIC — CALIBRATION & BENCHMARK TOOL")
    print("=" * 76)

    for path in image_paths:
        res = evaluate_image(path)
        if res:
            results.append(res)
            print(f"\n[+] Image: {res['path']}")
            print("-" * 76)
            print(f"  1. Error Level Analysis (ELA):")
            print(f"     - Score:        {res['ela']['score']:.4f}")
            print(f"     - Regions:      {res['ela']['regions_count']} flagged")
            print(f"     - Calibration:  {res['ela']['constants']}")
            print(f"  2. Copy-Move Detection:")
            print(f"     - Score:        {res['copy_move']['score']:.4f}")
            print(f"     - Regions:      {res['copy_move']['regions_count']} flagged")
            print(f"     - Calibration:  {res['copy_move']['constants']}")
            print(f"  3. Font Consistency:")
            print(f"     - Score:        {res['font_consistency']['score']:.4f}")
            print(f"     - Regions:      {res['font_consistency']['regions_count']} flagged")
            print(f"     - Calibration:  {res['font_consistency']['constants']}")
            print(f"  --> Combined Suspicion Score: {res['suspicion_score']:.4f} (simple average)")

    if len(results) >= 2:
        print("\n" + "=" * 76)
        print(" SIDE-BY-SIDE COMPARISON")
        print("=" * 76)
        print(f"{'Image':<32} {'ELA':<10} {'CopyMove':<10} {'Font':<10} {'Combined':<10}")
        print("-" * 76)
        for r in results:
            fname = os.path.basename(r["path"])
            if len(fname) > 30:
                fname = fname[:27] + "..."
            print(
                f"{fname:<32} "
                f"{r['ela']['score']:<10.4f} "
                f"{r['copy_move']['score']:<10.4f} "
                f"{r['font_consistency']['score']:<10.4f} "
                f"{r['suspicion_score']:<10.4f}"
            )
        print("=" * 76)
        print("Note: Tune divisors/thresholds if clean & tampered scores fail to separate cleanly.\n")


if __name__ == "__main__":
    main()
