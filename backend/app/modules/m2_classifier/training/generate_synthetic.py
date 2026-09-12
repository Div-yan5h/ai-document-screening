"""
M2 Classifier — Synthetic Training Data Generator (Task A)
==========================================================
Generates synthetic placeholder training data for:
- passport (aspect ratio ~1.42, photo box, MRZ band, specimen markings)
- visa (aspect ratio 1.20 - 1.34, security border, entry fields, specimen markings)
- unknown (non-document backgrounds, geometric shapes, abstract textures, noise)

Applies 5 augmentation families matching the real Aadhaar dataset:
- blurred
- contrast_adjusted
- hue_sat_adjusted
- scaled_up
- scaled_down

Builds a comprehensive dataset manifest (CSV) indexing both real Aadhaar images
(source=real) and generated images (source=synthetic).

Owner: P2
"""

import csv
import glob
import math
import os
import random
import re
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


def find_repo_root() -> str:
    curr = os.path.abspath(os.path.dirname(__file__))
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "new_generated_aadharcard_images")):
            return curr
        curr = os.path.dirname(curr)
    return os.path.abspath(os.getcwd())


PROJECT_ROOT = find_repo_root()
TRAINING_DIR = os.path.join(PROJECT_ROOT, "backend/app/modules/m2_classifier/training")
DATA_DIR = os.path.join(TRAINING_DIR, "data")
MANIFESTS_DIR = os.path.join(TRAINING_DIR, "manifests")
AADHAAR_DIR = os.path.join(PROJECT_ROOT, "new_generated_aadharcard_images")

# Seed for reproducible generation
RANDOM_SEED = 2026
random.seed(RANDOM_SEED)

FAKE_SURNAMES = [
    "DOE", "SMITH", "JOHNSON", "WILLIAMS", "BROWN", "JONES", "GARCIA", "MILLER",
    "DAVIS", "RODRIGUEZ", "MARTINEZ", "HERNANDEZ", "LOPEZ", "GONZALEZ", "WILSON",
    "ANDERSON", "THOMAS", "TAYLOR", "MOORE", "JACKSON", "MARTIN", "LEE", "PEREZ",
    "THOMPSON", "WHITE", "HARRIS", "SANCHEZ", "CLARK", "RAMIREZ", "LEWIS", "ROBINSON",
]

FAKE_GIVEN_NAMES = [
    "ALICE", "BOB", "CHARLIE", "DAVID", "EMMA", "FRANK", "GRACE", "HENRY", "ISABELLA",
    "JACK", "KATHERINE", "LEO", "MIA", "NOAH", "OLIVIA", "PETER", "QUINN", "ROSE",
    "SAMUEL", "TAYLOR", "VICTOR", "WENDY", "XAVIER", "YARA", "ZACHARY", "ALEXANDER",
]

FAKE_COUNTRIES = ["UTO", "SYN", "SMP", "DEM", "ATL", "GLB", "XAA", "XYX"]
FAKE_COUNTRY_NAMES = [
    "REPUBLIC OF UTOPIA", "FEDERATION OF SYNTHETICA", "SAMPLE JURISDICTION",
    "DEMO COMMONWEALTH", "ISLANDS OF ATLANTIS", "GLOBAL UNION SPECIMEN",
]


class PassportGenerator:
    """Generates synthetic passport images adhering to TD3 layout and ~1.42 aspect ratio."""

    BG_COLORS = [
        (238, 245, 252),  # pale blue
        (250, 248, 242),  # warm ivory
        (242, 248, 242),  # pale mint
        (253, 245, 242),  # soft peach
        (245, 245, 248),  # subtle lavender
        (244, 244, 244),  # light grey
    ]

    @classmethod
    def generate_base(cls, index: int) -> Image.Image:
        # TD3 passport aspect ratio: 125mm x 88mm = ~1.42
        width = random.choice([568, 596, 625, 639])
        height = int(round(width / random.uniform(1.40, 1.44)))
        bg_col = random.choice(cls.BG_COLORS)

        img = Image.new("RGB", (width, height), color=bg_col)
        draw = ImageDraw.Draw(img)

        # Outer document margin / border
        margin = random.randint(8, 14)
        doc_rect = [margin, margin, width - margin, height - margin]
        draw.rectangle(doc_rect, outline=(120, 140, 170), width=2)

        # Subtle guilloche / security pattern lines in background
        for y in range(margin + 10, height - margin - 80, random.randint(8, 15)):
            draw.line([(margin + 5, y), (width - margin - 5, y)], fill=(bg_col[0] - 8, bg_col[1] - 8, bg_col[2] - 8), width=1)

        # Header band
        country = random.choice(FAKE_COUNTRY_NAMES)
        draw.text((margin + 15, margin + 8), country, fill=(20, 40, 90))
        draw.text((margin + 15, margin + 26), "PASSPORT  /  PASSEPORT", fill=(70, 70, 70))

        # Photo placeholder box (Left side)
        photo_w = int(width * 0.26)
        photo_h = int(height * 0.48)
        photo_x = margin + 15
        photo_y = margin + 50
        draw.rectangle([photo_x, photo_y, photo_x + photo_w, photo_y + photo_h], fill=(215, 225, 235), outline=(90, 110, 140), width=2)
        # Silhouette placeholder
        head_r = int(photo_w * 0.22)
        cx, cy = photo_x + photo_w // 2, photo_y + int(photo_h * 0.35)
        draw.ellipse([cx - head_r, cy - head_r, cx + head_r, cy + head_r], fill=(160, 175, 195))
        draw.chord([cx - photo_w // 3, cy + head_r - 5, cx + photo_w // 3, photo_y + photo_h - 5], start=0, end=180, fill=(160, 175, 195))
        draw.text((photo_x + 10, photo_y + photo_h - 18), "SPECIMEN", fill=(100, 110, 130))

        # Fake field data
        surname = random.choice(FAKE_SURNAMES)
        given_name = random.choice(FAKE_GIVEN_NAMES)
        doc_num = f"X{random.randint(1000000, 9999999)}"
        nat = random.choice(FAKE_COUNTRIES)
        dob = f"{random.randint(1, 28):02d} {random.choice(['JAN','MAR','MAY','JUL','AUG','OCT','NOV'])} {random.randint(1965, 2003)}"
        issue_date = f"{random.randint(1, 28):02d} {random.choice(['FEB','APR','JUN','SEP'])} 2020"
        exp_date = f"{random.randint(1, 28):02d} {random.choice(['FEB','APR','JUN','SEP'])} 2030"
        sex = random.choice(["M", "F"])

        fields_x = photo_x + photo_w + 20
        fields = [
            f"Type/Type: P     Code: {nat}     Passport No: {doc_num}",
            f"Surname: {surname}",
            f"Given Names: {given_name}",
            f"Nationality: {nat} SPECIMEN",
            f"Date of Birth: {dob}",
            f"Sex: {sex}    Place of birth: SAMPLE CITY",
            f"Date of issue: {issue_date}",
            f"Date of expiry: {exp_date}",
        ]

        fy = photo_y + 2
        for line in fields:
            draw.text((fields_x, fy), line, fill=(15, 20, 35))
            fy += int(photo_h / len(fields))

        # Prominent SPECIMEN watermark
        draw.text((width // 2 - 80, height // 2 - 25), "SPECIMEN", fill=(200, 50, 50))
        draw.text((width // 2 - 120, height // 2 + 5), "NOT A REAL DOCUMENT", fill=(200, 50, 50))

        # Bottom MRZ Zone (lower ~22% of passport)
        mrz_h = int(height * 0.22)
        mrz_y = height - margin - mrz_h
        draw.rectangle([margin + 2, mrz_y, width - margin - 2, height - margin - 2], fill=(250, 250, 240), outline=(200, 200, 190))

        # 2 lines of fake OCR-B pattern
        dob_num = f"{random.randint(65, 99):02d}{random.randint(1,12):02d}{random.randint(1,28):02d}"
        exp_num = f"{random.randint(28, 35):02d}{random.randint(1,12):02d}{random.randint(1,28):02d}"
        mrz_line1 = f"P<{nat}{surname}<<{given_name}".ljust(44, "<")[:44]
        mrz_line2 = f"{doc_num}<{random.randint(0,9)}{nat}{dob_num}{random.randint(0,9)}{sex}{exp_num}{random.randint(0,9)}".ljust(44, "<")[:44]

        draw.text((margin + 18, mrz_y + 8), mrz_line1, fill=(10, 10, 10))
        draw.text((margin + 18, mrz_y + int(mrz_h * 0.5)), mrz_line2, fill=(10, 10, 10))

        return img


class VisaGenerator:
    """Generates synthetic visa images with aspect ratio ~1.20 - 1.34."""

    BG_COLORS = [
        (255, 243, 235),  # pale peach
        (240, 250, 245),  # light seafoam
        (248, 240, 252),  # pale lilac
        (255, 252, 235),  # soft cream yellow
        (238, 248, 252),  # pale cyan
    ]

    @classmethod
    def generate_base(cls, index: int) -> Image.Image:
        # Aspect ratio 1.20 to 1.34
        width = random.choice([580, 600, 620, 640])
        height = int(round(width / random.uniform(1.22, 1.32)))
        bg_col = random.choice(cls.BG_COLORS)

        img = Image.new("RGB", (width, height), color=bg_col)
        draw = ImageDraw.Draw(img)

        # Ornate / security patterned border
        border_inset = random.randint(6, 12)
        draw.rectangle([border_inset, border_inset, width - border_inset, height - border_inset], outline=(150, 100, 120), width=3)
        draw.rectangle([border_inset + 4, border_inset + 4, width - border_inset - 4, height - border_inset - 4], outline=(200, 160, 180), width=1)

        # Background security pattern lines
        for x in range(border_inset + 10, width - border_inset - 10, random.randint(15, 25)):
            draw.line([(x, border_inset + 5), (x, height - border_inset - 5)], fill=(bg_col[0] - 10, bg_col[1] - 10, bg_col[2] - 10), width=1)

        # Header
        title = random.choice(["VISA", "ENTRY VISA", "TOURIST VISA", "VISUM", "SAMPLE ENTRY PERMIT"])
        header_country = random.choice(FAKE_COUNTRY_NAMES)
        draw.text((border_inset + 15, border_inset + 8), header_country, fill=(90, 40, 60))
        draw.text((border_inset + 15, border_inset + 26), f"{title} — SPECIMEN ONLY", fill=(120, 30, 30))

        # Visa Number top right
        visa_no = f"V{random.randint(1000000, 9999999)}"
        draw.text((width - border_inset - 150, border_inset + 12), f"NO: {visa_no}", fill=(180, 20, 20))

        # Photo area (Right side or Left side)
        photo_on_right = random.choice([True, False])
        photo_w = int(width * 0.22)
        photo_h = int(height * 0.44)

        if photo_on_right:
            photo_x = width - border_inset - photo_w - 15
            fields_x = border_inset + 20
        else:
            photo_x = border_inset + 15
            fields_x = photo_x + photo_w + 18

        photo_y = border_inset + 50
        draw.rectangle([photo_x, photo_y, photo_x + photo_w, photo_y + photo_h], fill=(225, 220, 230), outline=(130, 90, 120), width=2)
        draw.text((photo_x + 10, photo_y + photo_h // 2 - 8), "PHOTO AREA", fill=(120, 110, 130))
        draw.text((photo_x + 15, photo_y + photo_h // 2 + 10), "SPECIMEN", fill=(120, 110, 130))

        # Visa field block
        surname = random.choice(FAKE_SURNAMES)
        given_name = random.choice(FAKE_GIVEN_NAMES)
        nat = random.choice(FAKE_COUNTRIES)
        valid_from = f"{random.randint(1, 28):02d}/03/2024"
        valid_until = f"{random.randint(1, 28):02d}/09/2024"
        num_entries = random.choice(["MULT", "01", "02"])
        pass_no = f"X{random.randint(1000000, 9999999)}"

        fields = [
            f"Valid From: {valid_from}   Until: {valid_until}",
            f"Type: C   Entries: {num_entries}   Stay: 90 DAYS",
            f"Issued at: SAMPLE CONSULATE",
            f"Passport No: {pass_no}",
            f"Surname, Name: {surname}, {given_name}",
            f"Nationality: {nat}",
            f"Remarks: SYNTHETIC TRAINING SPECIMEN",
        ]

        fy = photo_y + 4
        for line in fields:
            draw.text((fields_x, fy), line, fill=(20, 20, 30))
            fy += int(photo_h / len(fields))

        # Watermark
        draw.text((width // 2 - 100, height // 2 - 15), "SPECIMEN - NOT A REAL VISA", fill=(210, 60, 60))

        # Bottom serial band / MRV lines
        bottom_h = int(height * 0.18)
        bottom_y = height - border_inset - bottom_h
        draw.rectangle([border_inset + 2, bottom_y, width - border_inset - 2, height - border_inset - 2], fill=(245, 245, 238), outline=(210, 200, 210))
        mrv_line1 = f"V<UTO{surname}<<{given_name}".ljust(36, "<")[:36]
        mrv_line2 = f"{visa_no}<0UTO9001015M2409015<<<<<<<<<<0".ljust(36, "<")[:36]
        draw.text((border_inset + 25, bottom_y + 6), mrv_line1, fill=(20, 20, 20))
        draw.text((border_inset + 25, bottom_y + int(bottom_h * 0.5)), mrv_line2, fill=(20, 20, 20))

        return img


class UnknownGenerator:
    """Generates synthetic non-document / negative class images."""

    @classmethod
    def generate_base(cls, index: int) -> Image.Image:
        pattern_type = index % 5

        # Varied aspect ratios (0.8 to 1.6)
        width = random.randint(450, 650)
        aspect = random.choice([0.85, 1.0, 1.15, 1.35, 1.55])
        height = int(round(width / aspect))

        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        if pattern_type == 0:
            # Geometric shapes composition
            bg_col = (random.randint(220, 250), random.randint(220, 250), random.randint(220, 250))
            draw.rectangle([0, 0, width, height], fill=bg_col)
            for _ in range(random.randint(8, 16)):
                col = (random.randint(40, 220), random.randint(40, 220), random.randint(40, 220))
                shape_type = random.choice(["circle", "rect", "triangle", "line"])
                x1, y1 = random.randint(0, width - 40), random.randint(0, height - 40)
                x2, y2 = x1 + random.randint(20, 120), y1 + random.randint(20, 120)
                if shape_type == "circle":
                    draw.ellipse([x1, y1, x2, y2], fill=col)
                elif shape_type == "rect":
                    draw.rectangle([x1, y1, x2, y2], fill=col)
                elif shape_type == "triangle":
                    draw.polygon([(x1, y1), (x2, y1), ((x1 + x2) // 2, y2)], fill=col)
                else:
                    draw.line([(x1, y1), (x2, y2)], fill=col, width=random.randint(2, 6))

        elif pattern_type == 1:
            # Synthetic gradient / texture
            c1 = (random.randint(30, 100), random.randint(50, 120), random.randint(80, 150))
            c2 = (random.randint(180, 240), random.randint(190, 240), random.randint(200, 250))
            for y in range(height):
                ratio = y / max(height, 1)
                r = int(c1[0] * (1 - ratio) + c2[0] * ratio)
                g = int(c1[1] * (1 - ratio) + c2[1] * ratio)
                b = int(c1[2] * (1 - ratio) + c2[2] * ratio)
                draw.line([(0, y), (width, y)], fill=(r, g, b))

        elif pattern_type == 2:
            # Chart / diagram / abstract drawing (non-document)
            draw.rectangle([0, 0, width, height], fill=(248, 249, 250))
            # Draw axes
            draw.line([(50, height - 50), (width - 50, height - 50)], fill=(80, 80, 80), width=2)
            draw.line([(50, 50), (50, height - 50)], fill=(80, 80, 80), width=2)
            # Draw random bar chart or graph
            bar_w = (width - 140) // 8
            for bi in range(8):
                bx = 70 + bi * (bar_w + 6)
                bh = random.randint(40, height - 120)
                bcol = (random.randint(50, 200), random.randint(50, 200), random.randint(50, 200))
                draw.rectangle([bx, height - 50 - bh, bx + bar_w, height - 50], fill=bcol)
            draw.text((width // 2 - 60, 20), "SYNTHETIC CHART NON-DOC", fill=(100, 100, 100))

        elif pattern_type == 3:
            # Random digital noise / blocks
            draw.rectangle([0, 0, width, height], fill=(230, 230, 230))
            step = random.randint(15, 30)
            for x in range(0, width, step):
                for y in range(0, height, step):
                    val = random.randint(90, 240)
                    draw.rectangle([x, y, x + step, y + step], fill=(val, val, val))

        else:
            # Blank / minimal non-document page with random doodle
            draw.rectangle([0, 0, width, height], fill=(random.randint(240, 255), random.randint(240, 255), random.randint(240, 255)))
            for _ in range(random.randint(4, 10)):
                pts = [(random.randint(20, width - 20), random.randint(20, height - 20)) for _ in range(3)]
                draw.line(pts, fill=(random.randint(50, 180), random.randint(50, 180), random.randint(50, 180)), width=random.randint(1, 4))
            draw.text((20, 20), "NON-DOCUMENT SPECIMEN", fill=(180, 180, 180))

        return img


class Augmenter:
    """Applies the 5 augmentation families used by the real Aadhaar dataset."""

    @staticmethod
    def apply_blurred(img: Image.Image) -> Image.Image:
        radius = random.uniform(1.8, 2.8)
        return img.filter(ImageFilter.GaussianBlur(radius=radius))

    @staticmethod
    def apply_contrast_adjusted(img: Image.Image) -> Image.Image:
        factor = random.choice([random.uniform(0.60, 0.75), random.uniform(1.35, 1.65)])
        enhancer = ImageEnhance.Contrast(img)
        return enhancer.enhance(factor)

    @staticmethod
    def apply_hue_sat_adjusted(img: Image.Image) -> Image.Image:
        factor = random.choice([random.uniform(0.35, 0.65), random.uniform(1.4, 1.85)])
        enhancer = ImageEnhance.Color(img)
        return enhancer.enhance(factor)

    @staticmethod
    def apply_scaled_up(img: Image.Image) -> Image.Image:
        w, h = img.size
        factor = random.uniform(1.20, 1.30)
        new_w, new_h = int(w * factor), int(h * factor)
        return img.resize((new_w, new_h), Image.Resampling.BILINEAR)

    @staticmethod
    def apply_scaled_down(img: Image.Image) -> Image.Image:
        w, h = img.size
        factor = random.uniform(0.70, 0.80)
        new_w, new_h = int(w * factor), int(h * factor)
        return img.resize((new_w, new_h), Image.Resampling.BILINEAR)


def generate_class_data(
    cls_name: str,
    generator_fn: Any,
    count: int = 200,
) -> List[Dict[str, str]]:
    """Generates base images and 5 augmentations per base image for a given class."""
    cls_dir = os.path.join(DATA_DIR, cls_name)
    os.makedirs(cls_dir, exist_ok=True)

    records: List[Dict[str, str]] = []

    for i in range(1, count + 1):
        base_id = f"{cls_name}_{i:03d}"
        base_img = generator_fn(i)

        # 1. Base / original image
        base_filename = f"{base_id}_base.png"
        base_path = os.path.join(cls_dir, base_filename)
        base_img.save(base_path)
        records.append({
            "path": os.path.relpath(base_path, PROJECT_ROOT).replace("\\", "/"),
            "class": cls_name,
            "source": "synthetic",
            "base_id": base_id,
            "augmentation": "original",
        })

        # 2. Blurred
        blurred_img = Augmenter.apply_blurred(base_img)
        blurred_filename = f"{base_id}_blurred.png"
        blurred_path = os.path.join(cls_dir, blurred_filename)
        blurred_img.save(blurred_path)
        records.append({
            "path": os.path.relpath(blurred_path, PROJECT_ROOT).replace("\\", "/"),
            "class": cls_name,
            "source": "synthetic",
            "base_id": base_id,
            "augmentation": "blurred",
        })

        # 3. Contrast adjusted
        contrast_img = Augmenter.apply_contrast_adjusted(base_img)
        contrast_filename = f"{base_id}_contrast_adjusted.png"
        contrast_path = os.path.join(cls_dir, contrast_filename)
        contrast_img.save(contrast_path)
        records.append({
            "path": os.path.relpath(contrast_path, PROJECT_ROOT).replace("\\", "/"),
            "class": cls_name,
            "source": "synthetic",
            "base_id": base_id,
            "augmentation": "contrast_adjusted",
        })

        # 4. Hue/sat adjusted
        hue_sat_img = Augmenter.apply_hue_sat_adjusted(base_img)
        hue_sat_filename = f"{base_id}_hue_sat_adjusted.png"
        hue_sat_path = os.path.join(cls_dir, hue_sat_filename)
        hue_sat_img.save(hue_sat_path)
        records.append({
            "path": os.path.relpath(hue_sat_path, PROJECT_ROOT).replace("\\", "/"),
            "class": cls_name,
            "source": "synthetic",
            "base_id": base_id,
            "augmentation": "hue_sat_adjusted",
        })

        # 5. Scaled up
        scaled_up_img = Augmenter.apply_scaled_up(base_img)
        scaled_up_filename = f"{base_id}_scaled_up.png"
        scaled_up_path = os.path.join(cls_dir, scaled_up_filename)
        scaled_up_img.save(scaled_up_path)
        records.append({
            "path": os.path.relpath(scaled_up_path, PROJECT_ROOT).replace("\\", "/"),
            "class": cls_name,
            "source": "synthetic",
            "base_id": base_id,
            "augmentation": "scaled_up",
        })

        # 6. Scaled down
        scaled_down_img = Augmenter.apply_scaled_down(base_img)
        scaled_down_filename = f"{base_id}_scaled_down.png"
        scaled_down_path = os.path.join(cls_dir, scaled_down_filename)
        scaled_down_img.save(scaled_down_path)
        records.append({
            "path": os.path.relpath(scaled_down_path, PROJECT_ROOT).replace("\\", "/"),
            "class": cls_name,
            "source": "synthetic",
            "base_id": base_id,
            "augmentation": "scaled_down",
        })

    return records


def index_real_aadhaar_dataset() -> List[Dict[str, str]]:
    """Indexes the existing 1000 real Aadhaar images."""
    files = glob.glob(os.path.join(AADHAAR_DIR, "*.jpg"))
    records: List[Dict[str, str]] = []

    for file_path in sorted(files):
        fname = os.path.basename(file_path)
        # Parse e.g. '107front_blurred.jpg' -> doc_id='107', side='front', aug='blurred'
        m = re.match(r"^(\d+)(front|backside)_(.*)\.jpg$", fname)
        if m:
            doc_id = m.group(1)
            side = m.group(2)
            aug = m.group(3)
            base_id = f"{doc_id}{side}"
        else:
            base_id = os.path.splitext(fname)[0]
            aug = "original"

        records.append({
            "path": os.path.relpath(file_path, PROJECT_ROOT).replace("\\", "/"),
            "class": "id_card",
            "source": "real",
            "base_id": base_id,
            "augmentation": aug,
        })

    return records


def main():
    print("=== M2 TRAINING TASK A: SYNTHETIC DATA GENERATION ===")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(MANIFESTS_DIR, exist_ok=True)

    # 1. Generate Synthetic Passports (200 base + 5 aug each = 1200 images)
    print("Generating synthetic passport data (200 base images)...")
    passport_records = generate_class_data("passport", PassportGenerator.generate_base, count=200)
    print(f"Generated {len(passport_records)} passport images.")

    # 2. Generate Synthetic Visas (200 base + 5 aug each = 1200 images)
    print("Generating synthetic visa data (200 base images)...")
    visa_records = generate_class_data("visa", VisaGenerator.generate_base, count=200)
    print(f"Generated {len(visa_records)} visa images.")

    # 3. Generate Synthetic Unknowns (200 base + 5 aug each = 1200 images)
    print("Generating synthetic unknown data (200 base images)...")
    unknown_records = generate_class_data("unknown", UnknownGenerator.generate_base, count=200)
    print(f"Generated {len(unknown_records)} unknown images.")

    # 4. Index Real Aadhaar Dataset
    print("Indexing real Aadhaar dataset...")
    aadhaar_records = index_real_aadhaar_dataset()
    print(f"Indexed {len(aadhaar_records)} real Aadhaar images.")

    # 5. Build Combined Manifest
    all_records = passport_records + visa_records + aadhaar_records + unknown_records
    manifest_path = os.path.join(MANIFESTS_DIR, "dataset_manifest.csv")

    fieldnames = ["path", "class", "source", "base_id", "augmentation"]
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_records)

    print(f"Dataset manifest written to: {manifest_path}")
    print(f"Total entries in manifest: {len(all_records)}")

    # 6. Quality Checks
    print("\n--- Running Quality Verification Checks ---")
    corrupt_count = 0
    for rec in all_records:
        full_path = os.path.join(PROJECT_ROOT, rec["path"])
        if not os.path.exists(full_path):
            print(f"ERROR: Missing file: {full_path}")
            corrupt_count += 1
            continue
        try:
            with Image.open(full_path) as im:
                im.verify()
        except Exception as e:
            print(f"ERROR: Cannot open/verify {full_path}: {e}")
            corrupt_count += 1

    assert corrupt_count == 0, f"Quality check failed: {corrupt_count} corrupt files found!"
    print(f"All {len(all_records)} images successfully verified and opened!")
    print("Task A completed successfully!")


if __name__ == "__main__":
    main()
