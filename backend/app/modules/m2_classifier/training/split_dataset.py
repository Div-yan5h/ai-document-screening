"""
M2 Classifier — Leakage-Safe Train/Validation Split (Task B)
============================================================
Performs a deterministic, group-based, stratified 80/20 train/validation split
across all 4 classes: passport, visa, id_card, and unknown.

Guarantees:
1. Group-Based Splitting: All augmented variations and document sides (front/back)
   of the same underlying document/identity stay strictly within either TRAIN or VAL.
2. Parent Document Grouping for Aadhaar: Front and backside images sharing the same
   Aadhaar document ID (e.g. 107front, 107backside) are bound to the parent split_group '107'.
3. Zero Data Leakage: set(train_groups) & set(val_groups) == empty for every class.
4. Exactly 80/20 Stratification: Preserves class balance and real/synthetic proportions.
5. Deterministic & Reproducible: Fixed seed = 42.

Outputs:
- train_manifest.csv
- val_manifest.csv
- group_split_audit.csv

Owner: P2
"""

import csv
import os
import random
import re
from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple


def find_repo_root() -> str:
    curr = os.path.abspath(os.path.dirname(__file__))
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "new_generated_aadharcard_images")):
            return curr
        curr = os.path.dirname(curr)
    return os.path.abspath(os.getcwd())


PROJECT_ROOT = find_repo_root()
TRAINING_DIR = os.path.join(PROJECT_ROOT, "backend/app/modules/m2_classifier/training")
MANIFESTS_DIR = os.path.join(TRAINING_DIR, "manifests")
DATASET_MANIFEST_PATH = os.path.join(MANIFESTS_DIR, "dataset_manifest.csv")
TRAIN_MANIFEST_PATH = os.path.join(MANIFESTS_DIR, "train_manifest.csv")
VAL_MANIFEST_PATH = os.path.join(MANIFESTS_DIR, "val_manifest.csv")
AUDIT_MANIFEST_PATH = os.path.join(MANIFESTS_DIR, "group_split_audit.csv")

SEED = 42


def get_split_group(row: Dict[str, str]) -> str:
    """
    Determines the parent document identity (split_group) to prevent data leakage.
    - For Aadhaar (id_card): extracts parent numeric doc_id (e.g. '107' from '107front_blurred.jpg').
      Both front and backside share the same parent document ID.
    - For synthetic classes (passport, visa, unknown): uses base_id (e.g. 'passport_001').
    """
    cls = row["class"]
    if cls == "id_card":
        fname = os.path.basename(row["path"])
        m = re.match(r"^(\d+)", fname)
        if m:
            return f"aadhar_{m.group(1)}"
        return f"aadhar_{row['base_id']}"
    return row["base_id"]


def split_dataset():
    print("=== M2 TRAINING TASK B: LEAKAGE-SAFE TRAIN/VALIDATION SPLIT ===")

    # 1. Read existing manifest
    assert os.path.exists(DATASET_MANIFEST_PATH), f"Manifest not found: {DATASET_MANIFEST_PATH}"
    with open(DATASET_MANIFEST_PATH, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    print(f"Loaded {len(reader)} rows from dataset_manifest.csv")
    assert len(reader) == 4600, f"Expected 4600 rows, found {len(reader)}"

    # 2. Enrich rows with split_group and group by class
    class_groups = defaultdict(lambda: defaultdict(list))
    for row in reader:
        sg = get_split_group(row)
        row["split_group"] = sg
        class_groups[row["class"]][sg].append(row)

    train_rows: List[Dict[str, str]] = []
    val_rows: List[Dict[str, str]] = []
    audit_rows: List[Dict[str, Any]] = []

    classes = ["passport", "visa", "id_card", "unknown"]

    # 3. Perform group-based 80/20 split per class with deterministic seed
    rng = random.Random(SEED)

    print("\n--- Performing Stratified 80/20 Group-Based Split ---")
    summary_table = []

    for cls in classes:
        groups_dict = class_groups[cls]
        # Deterministic sorting before shuffle
        group_keys = sorted(list(groups_dict.keys()))
        rng.shuffle(group_keys)

        total_groups = len(group_keys)
        n_train_groups = int(round(total_groups * 0.80))
        n_val_groups = total_groups - n_train_groups

        train_keys = set(group_keys[:n_train_groups])
        val_keys = set(group_keys[n_train_groups:])

        # Strict assertion: no overlap between train and val groups
        assert len(train_keys & val_keys) == 0, f"Leakage detected in class {cls}!"
        assert len(train_keys) + len(val_keys) == total_groups

        cls_train_imgs = 0
        cls_val_imgs = 0

        for gk in group_keys:
            img_rows = groups_dict[gk]
            is_train = gk in train_keys
            split_label = "train" if is_train else "validation"

            for r in img_rows:
                if is_train:
                    train_rows.append(r)
                    cls_train_imgs += 1
                else:
                    val_rows.append(r)
                    cls_val_imgs += 1

            source = img_rows[0]["source"]
            audit_rows.append({
                "class": cls,
                "split_group": gk,
                "split": split_label,
                "source": source,
                "image_count": len(img_rows),
            })

        summary_table.append({
            "class": cls,
            "train_groups": n_train_groups,
            "val_groups": n_val_groups,
            "total_groups": total_groups,
            "train_images": cls_train_imgs,
            "val_images": cls_val_imgs,
            "total_images": cls_train_imgs + cls_val_imgs,
        })

    # 4. Write train_manifest.csv and val_manifest.csv
    fieldnames = ["path", "class", "source", "base_id", "augmentation", "split_group"]

    with open(TRAIN_MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(train_rows)

    with open(VAL_MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(val_rows)

    # 5. Write group_split_audit.csv
    audit_fields = ["class", "split_group", "split", "source", "image_count"]
    # Sort audit rows by class, then split_group for easy auditing
    audit_rows.sort(key=lambda x: (x["class"], x["split_group"]))
    with open(AUDIT_MANIFEST_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=audit_fields)
        writer.writeheader()
        writer.writerows(audit_rows)

    # 6. Leakage & Quality Assertions
    print("\n--- Running Leakage & Quality Verifications ---")

    # A. Total image count equality
    assert len(train_rows) + len(val_rows) == len(reader) == 4600, "Image count mismatch!"

    # B. Path uniqueness & disjointness
    train_paths = set(r["path"] for r in train_rows)
    val_paths = set(r["path"] for r in val_rows)
    assert len(train_paths) == len(train_rows), "Duplicate path in train_manifest!"
    assert len(val_paths) == len(val_rows), "Duplicate path in val_manifest!"
    assert len(train_paths & val_paths) == 0, "Path overlap detected across splits!"

    # C. Split group disjointness
    train_groups_all = set(r["split_group"] for r in train_rows)
    val_groups_all = set(r["split_group"] for r in val_rows)
    assert len(train_groups_all & val_groups_all) == 0, "Group leakage detected across splits!"

    # D. Aadhaar front/back co-location verification
    # Verify that front and backside of any Aadhaar document ID NEVER cross train/val
    aadhar_train_docs = set(re.match(r"^(\d+)", os.path.basename(r["path"])).group(1) for r in train_rows if r["class"] == "id_card")
    aadhar_val_docs = set(re.match(r"^(\d+)", os.path.basename(r["path"])).group(1) for r in val_rows if r["class"] == "id_card")
    assert len(aadhar_train_docs & aadhar_val_docs) == 0, "Aadhaar parent document leakage detected!"
    print("Aadhaar front/back co-location check PASSED (zero cross-split leakage).")

    # 7. Print summary tables
    print("\n" + "=" * 75)
    print(f"{'CLASS':<12} {'TRAIN GROUPS':<14} {'VAL GROUPS':<12} {'TRAIN IMAGES':<14} {'VAL IMAGES':<12} {'TOTAL'}")
    print("-" * 75)
    for st in summary_table:
        print(f"{st['class']:<12} {st['train_groups']:<14} {st['val_groups']:<12} {st['train_images']:<14} {st['val_images']:<12} {st['total_images']}")
    print("-" * 75)
    tot_tr_grp = sum(st['train_groups'] for st in summary_table)
    tot_val_grp = sum(st['val_groups'] for st in summary_table)
    tot_tr_img = sum(st['train_images'] for st in summary_table)
    tot_val_img = sum(st['val_images'] for st in summary_table)
    print(f"{'TOTAL':<12} {tot_tr_grp:<14} {tot_val_grp:<12} {tot_tr_img:<14} {tot_val_img:<12} {tot_tr_img + tot_val_img}")
    print("=" * 75)

    real_train = sum(1 for r in train_rows if r["source"] == "real")
    real_val = sum(1 for r in val_rows if r["source"] == "real")
    synth_train = sum(1 for r in train_rows if r["source"] == "synthetic")
    synth_val = sum(1 for r in val_rows if r["source"] == "synthetic")

    print("\nREAL (Aadhaar id_card):")
    print(f"  train images      = {real_train} ({real_train / (real_train + real_val) * 100:.1f}%)")
    print(f"  validation images = {real_val} ({real_val / (real_train + real_val) * 100:.1f}%)")

    print("\nSYNTHETIC (passport, visa, unknown):")
    print(f"  train images      = {synth_train} ({synth_train / (synth_train + synth_val) * 100:.1f}%)")
    print(f"  validation images = {synth_val} ({synth_val / (synth_train + synth_val) * 100:.1f}%)")

    print(f"\nManifests generated successfully:")
    print(f"  Train Manifest: {TRAIN_MANIFEST_PATH}")
    print(f"  Val Manifest:   {VAL_MANIFEST_PATH}")
    print(f"  Audit Manifest: {AUDIT_MANIFEST_PATH}")


if __name__ == "__main__":
    split_dataset()
