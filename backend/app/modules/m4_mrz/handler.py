"""
M4 — MRZ Parser + Cross-Check
==============================
Detects the MRZ zone in a document image, runs a dedicated OCR pass
on the cropped MRZ region, parses fixed-width ICAO Doc 9303 fields,
validates check digits, and cross-checks against M3 OCR output.

Supports:
  - TD3 (passport):  2 lines × 44 characters
  - TD1 (ID card):   3 lines × 30 characters

Owner: P3

Dependencies: opencv-python, pytesseract (+ Tesseract binary), numpy, Pillow
"""

from __future__ import annotations

import logging
import os
import re
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import pytesseract
from PIL import Image

from backend.app.schemas.contracts import IngestionOutput, MRZOutput, OCROutput

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

# Valid MRZ characters: uppercase letters, digits, filler '<'
_MRZ_CHAR_PATTERN = re.compile(r"^[A-Z0-9<]+$")

# ICAO check-digit weights, repeated cyclically
_WEIGHTS = (7, 3, 1)

# Character → numeric value mapping for ICAO checksum
# '<' (filler) = 0, '0'-'9' = 0-9, 'A'-'Z' = 10-35
_CHAR_VALUES: Dict[str, int] = {"<": 0}
for _i in range(10):
    _CHAR_VALUES[str(_i)] = _i
for _i, _c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ", start=10):
    _CHAR_VALUES[_c] = _i

# Common OCR misreadings in MRZ context and their corrections.
# Applied selectively based on whether a position expects a letter or digit.
_OCR_DIGIT_FIXES = {"O": "0", "I": "1", "B": "8", "S": "5", "G": "6", "Z": "2"}
_OCR_ALPHA_FIXES = {"0": "O", "1": "I", "8": "B", "5": "S", "6": "G", "2": "Z"}


# ─────────────────────────────────────────────
# ICAO Doc 9303 Checksum
# ─────────────────────────────────────────────

def _compute_check_digit(data: str) -> int:
    """
    Compute an ICAO Doc 9303 check digit.

    Algorithm: for each character in *data*, look up its numeric value
    (A=10 … Z=35, 0-9=0-9, <=0), multiply by the cycling weight
    (7, 3, 1, 7, 3, 1, …), sum all products, return sum mod 10.
    """
    total = 0
    for i, ch in enumerate(data):
        val = _CHAR_VALUES.get(ch)
        if val is None:
            # Invalid character — treat as 0 but this signals a problem
            logger.warning("Invalid MRZ character '%s' at position %d during checksum", ch, i)
            val = 0
        total += val * _WEIGHTS[i % 3]
    return total % 10


def _verify_check_digit(data: str, expected_digit: str) -> bool:
    """Return True if the computed check digit over *data* matches *expected_digit*."""
    try:
        expected = int(expected_digit)
    except (ValueError, TypeError):
        return False
    return _compute_check_digit(data) == expected


# ─────────────────────────────────────────────
# OCR Normalization Helpers
# ─────────────────────────────────────────────

def _normalize_mrz_char(ch: str, expect_digit: bool) -> str:
    """
    Fix common OCR misreads based on whether a digit or letter is expected.

    For example, if we expect a digit and see 'O', replace with '0'.
    If we expect a letter and see '0', replace with 'O'.
    """
    ch = ch.upper()
    if expect_digit:
        return _OCR_DIGIT_FIXES.get(ch, ch)
    else:
        return _OCR_ALPHA_FIXES.get(ch, ch)


def _normalize_mrz_line(line: str) -> str:
    """
    Basic cleanup of a raw OCR line to look more like valid MRZ.

    - Uppercase
    - Strip whitespace
    - Replace common non-MRZ characters
    """
    line = line.upper().strip()
    # Common OCR artifacts: replace spaces, underscores, dashes in filler zones
    line = line.replace(" ", "")
    # Some OCR engines read '<' as '(' or 'K' in filler zones — careful replacement
    # We don't do aggressive replacement here; field-level normalization handles specifics.
    return line


def _normalize_date_field(raw: str) -> str:
    """
    Normalize a 6-character MRZ date field (YYMMDD).
    Apply digit-context OCR fixes to each character.
    """
    return "".join(_normalize_mrz_char(ch, expect_digit=True) for ch in raw)


def _normalize_doc_number_field(raw: str) -> str:
    """
    Normalize a document number field.
    The first character is typically a letter, rest can be alphanumeric.
    We don't aggressively normalize here — just clean non-MRZ chars.
    """
    return raw.upper().strip().replace(" ", "")


# ─────────────────────────────────────────────
# MRZ Zone Detection (OpenCV)
# ─────────────────────────────────────────────

def _detect_mrz_region(image_path: str) -> Optional[np.ndarray]:
    """
    Detect and crop the MRZ region from a document image using
    morphological operations.

    Strategy:
      1. Convert to grayscale.
      2. Apply blackhat morphology to reveal dark text on light background.
      3. Compute Scharr gradient magnitude to highlight text edges.
      4. Apply a closing morphology with a wide horizontal kernel to merge
         MRZ characters into a continuous block.
      5. Threshold + erode/dilate to clean up.
      6. Find contours and pick the one near the bottom of the image
         with an aspect ratio consistent with an MRZ band.
      7. Crop and return the MRZ region.

    Returns None if no MRZ-like region is found.
    """
    img = cv2.imread(image_path)
    if img is None:
        logger.warning("Could not load image: %s", image_path)
        return None

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # --- Step 1: Blackhat to isolate dark regions on light bg ---
    rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (13, 5))
    blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, rect_kernel)

    # --- Step 2: Scharr gradient (horizontal) to find text edges ---
    grad_x = cv2.Scharr(blackhat, ddepth=cv2.CV_32F, dx=1, dy=0)
    grad_x = np.absolute(grad_x)
    min_val, max_val = grad_x.min(), grad_x.max()
    if max_val - min_val > 0:
        grad_x = ((grad_x - min_val) / (max_val - min_val) * 255).astype(np.uint8)
    else:
        grad_x = np.zeros_like(gray)

    # --- Step 3: Close gaps between characters with wide horizontal kernel ---
    close_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 5))
    closed = cv2.morphologyEx(grad_x, cv2.MORPH_CLOSE, close_kernel)

    # --- Step 4: Threshold ---
    _, thresh = cv2.threshold(closed, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)

    # --- Step 5: Additional closing + erosion to form solid blocks ---
    close_kernel2 = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 7))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, close_kernel2)
    erode_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    thresh = cv2.erode(thresh, erode_kernel, iterations=2)
    thresh = cv2.dilate(thresh, None, iterations=2)

    # --- Step 6: Find contours, filter for MRZ-like shape near bottom ---
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates: List[Tuple[int, int, int, int, float]] = []
    for cnt in contours:
        x, y, cw, ch_c = cv2.boundingRect(cnt)
        aspect_ratio = cw / float(ch_c) if ch_c > 0 else 0
        # MRZ band: wide (aspect ratio > 5), at least 50% of image width,
        # located in bottom 50% of the image
        if aspect_ratio > 4 and cw > w * 0.4 and y > h * 0.4:
            candidates.append((x, y, cw, ch_c, aspect_ratio))

    if not candidates:
        logger.info("No MRZ-like contour found in image")
        return None

    # Pick the candidate closest to the bottom (highest y)
    candidates.sort(key=lambda c: c[1], reverse=True)

    # Expand the bounding box slightly for better OCR
    x, y, cw, ch_c, _ = candidates[0]
    pad_y = int(ch_c * 0.4)
    pad_x = int(cw * 0.02)
    y1 = max(0, y - pad_y)
    y2 = min(h, y + ch_c + pad_y)
    x1 = max(0, x - pad_x)
    x2 = min(w, x + cw + pad_x)

    mrz_crop = gray[y1:y2, x1:x2]

    # Quick size sanity check
    if mrz_crop.shape[0] < 10 or mrz_crop.shape[1] < 50:
        logger.info("Detected MRZ region too small: %s", mrz_crop.shape)
        return None

    return mrz_crop


# ─────────────────────────────────────────────
# Dedicated MRZ OCR (Tesseract)
# ─────────────────────────────────────────────

def _ocr_mrz_region(mrz_image: np.ndarray) -> str:
    """
    Run Tesseract OCR on a cropped MRZ region.

    Uses config optimized for MRZ:
      - PSM 6: assume a single uniform block of text
      - Whitelist: A-Z, 0-9, <
      - English language
    """
    # Enhance contrast for OCR
    mrz_enhanced = cv2.resize(mrz_image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, mrz_enhanced = cv2.threshold(
        mrz_enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )

    # Convert to PIL Image for pytesseract
    pil_image = Image.fromarray(mrz_enhanced)

    custom_config = (
        "--psm 6 "
        "-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"
    )
    try:
        raw_text = pytesseract.image_to_string(pil_image, config=custom_config)
    except pytesseract.TesseractNotFoundError:
        logger.error("Tesseract binary not found — cannot perform dedicated MRZ OCR")
        return ""
    except Exception as e:
        logger.error("Tesseract OCR failed: %s", e)
        return ""

    return raw_text


# ─────────────────────────────────────────────
# MRZ Line Extraction & Validation
# ─────────────────────────────────────────────

def _extract_mrz_lines_from_text(raw_text: str) -> Optional[List[str]]:
    """
    Extract valid MRZ lines from raw OCR text.

    Looks for lines that:
      - Contain only valid MRZ characters (A-Z, 0-9, <)
      - Are at least 28 characters long (TD1 = 30, TD3 = 44)
      - Appear in groups of 2 (TD3) or 3 (TD1)

    Returns the normalized MRZ lines if a valid group is found, else None.
    """
    if not raw_text:
        return None

    lines = raw_text.strip().split("\n")
    mrz_candidates: List[str] = []

    for line in lines:
        cleaned = _normalize_mrz_line(line)
        # Must be at least 28 chars and look like MRZ
        if len(cleaned) >= 28 and _MRZ_CHAR_PATTERN.match(cleaned):
            mrz_candidates.append(cleaned)

    if not mrz_candidates:
        return None

    # Try to find a TD3 group (2 lines of 44 chars)
    td3_lines = [l for l in mrz_candidates if len(l) >= 42]  # allow slight OCR length variation
    if len(td3_lines) >= 2:
        # Take the last 2 lines (MRZ is at the bottom)
        result = td3_lines[-2:]
        # Pad or trim to exactly 44
        result = [_pad_or_trim(l, 44) for l in result]
        return result

    # Try to find a TD1 group (3 lines of 30 chars)
    td1_lines = [l for l in mrz_candidates if 28 <= len(l) <= 36]
    if len(td1_lines) >= 3:
        result = td1_lines[-3:]
        result = [_pad_or_trim(l, 30) for l in result]
        return result

    # If we have exactly 2 lines of ~30 chars, treat as TD2 (same parse as TD3 subset)
    td2_lines = [l for l in mrz_candidates if 28 <= len(l) <= 40]
    if len(td2_lines) >= 2:
        # TD2: 2 lines × 36 chars — less common, but handle gracefully
        result = td2_lines[-2:]
        return result

    logger.info("Found %d MRZ-candidate lines but no valid TD1/TD3 group", len(mrz_candidates))
    return None


def _pad_or_trim(line: str, target_len: int) -> str:
    """Pad with '<' or trim to exactly *target_len* characters."""
    if len(line) < target_len:
        return line + "<" * (target_len - len(line))
    return line[:target_len]


# ─────────────────────────────────────────────
# TD3 (Passport) Parser — 2 lines × 44 chars
# ─────────────────────────────────────────────
#
# Line 1 (44 chars):
#   [0]      Document type first char (P)
#   [1]      Document type second char (or <)
#   [2:5]    Issuing state (3-letter code)
#   [5:44]   Surname<<Given<Names (rest of line, padded with <)
#
# Line 2 (44 chars):
#   [0:9]    Document number
#   [9]      Check digit (doc number)
#   [10:13]  Nationality (3-letter code)
#   [13:19]  Date of birth (YYMMDD)
#   [19]     Check digit (DOB)
#   [20]     Sex (M/F/<)
#   [21:27]  Expiry date (YYMMDD)
#   [27]     Check digit (expiry)
#   [28:42]  Optional data (personal number etc.)
#   [42]     Check digit (optional data)
#   [43]     Composite check digit (over positions 0-10, 13-20, 21-43 of line 2)

def _parse_td3(lines: List[str]) -> Optional[Dict]:
    """
    Parse a TD3 (passport) MRZ from two 44-character lines.

    Returns a dict with parsed fields and checksum validity,
    or None if the structure is clearly invalid.
    """
    if len(lines) < 2 or len(lines[0]) != 44 or len(lines[1]) != 44:
        return None

    line1, line2 = lines[0], lines[1]

    # --- Line 1: document type, issuing state, name ---
    doc_type_raw = line1[0:2].replace("<", "")
    if not doc_type_raw.startswith("P"):
        # Not a passport MRZ — might still be valid, but unexpected for TD3
        logger.info("TD3 line1 does not start with 'P': '%s'", doc_type_raw)

    issuing_state = line1[2:5].replace("<", "")
    name_section = line1[5:44]

    # Name: surname and given names separated by '<<'
    surname, given_names = _parse_mrz_name(name_section)

    # --- Line 2: doc number, nationality, DOB, sex, expiry, optional, checksums ---
    doc_number_raw = line2[0:9]
    doc_number_check = line2[9]
    nationality = line2[10:13].replace("<", "")
    dob_raw = line2[13:19]
    dob_check = line2[19]
    sex = line2[20]
    expiry_raw = line2[21:27]
    expiry_check = line2[27]
    optional_data = line2[28:42]
    optional_check = line2[42]
    composite_check = line2[43]

    # Normalize date fields (fix common OCR misreads in digit positions)
    dob_normalized = _normalize_date_field(dob_raw)
    expiry_normalized = _normalize_date_field(expiry_raw)
    doc_number = _normalize_doc_number_field(doc_number_raw)

    # --- Checksum validation ---
    checksums_ok = True

    # Check digit 1: document number (positions 0-8 of line2)
    if not _verify_check_digit(doc_number_raw, doc_number_check):
        logger.info("TD3 document number check digit failed")
        checksums_ok = False

    # Check digit 2: date of birth (positions 13-18 of line2)
    if not _verify_check_digit(dob_raw, dob_check):
        logger.info("TD3 DOB check digit failed")
        checksums_ok = False

    # Check digit 3: expiry date (positions 21-26 of line2)
    if not _verify_check_digit(expiry_raw, expiry_check):
        logger.info("TD3 expiry check digit failed")
        checksums_ok = False

    # Check digit 4: optional data (positions 28-41 of line2)
    # Only validate if optional data is not all filler
    if optional_data.replace("<", ""):
        if not _verify_check_digit(optional_data, optional_check):
            logger.info("TD3 optional data check digit failed")
            checksums_ok = False

    # Composite check digit: over doc_number+check + DOB+check + expiry+check + optional+check
    composite_data = line2[0:10] + line2[13:20] + line2[21:43]
    if not _verify_check_digit(composite_data, composite_check):
        logger.info("TD3 composite check digit failed")
        checksums_ok = False

    # --- Build result ---
    doc_number_clean = doc_number.replace("<", "").strip()

    fields = {
        "doc_type": doc_type_raw if doc_type_raw else "P",
        "issuing_state": issuing_state,
        "name": f"{surname} {given_names}".strip(),
        "surname": surname,
        "given_names": given_names,
        "doc_number": doc_number_clean,
        "nationality": nationality,
        "dob": _format_mrz_date(dob_normalized),
        "sex": sex if sex in ("M", "F") else "",
        "expiry_date": _format_mrz_date(expiry_normalized),
    }

    return {"fields": fields, "checksum_valid": checksums_ok, "format": "TD3"}


# ─────────────────────────────────────────────
# TD1 (ID Card) Parser — 3 lines × 30 chars
# ─────────────────────────────────────────────
#
# Line 1 (30 chars):
#   [0:2]    Document type (e.g. "I<", "ID", "AC")
#   [2:5]    Issuing state
#   [5:14]   Document number
#   [14]     Check digit (doc number)
#   [15:30]  Optional data 1
#
# Line 2 (30 chars):
#   [0:6]    Date of birth (YYMMDD)
#   [6]      Check digit (DOB)
#   [7]      Sex (M/F/<)
#   [8:14]   Expiry date (YYMMDD)
#   [14]     Check digit (expiry)
#   [15:18]  Nationality
#   [18:29]  Optional data 2
#   [29]     Composite check digit
#
# Line 3 (30 chars):
#   [0:30]   Name: Surname<<Given<Names<<<...

def _parse_td1(lines: List[str]) -> Optional[Dict]:
    """
    Parse a TD1 (ID card) MRZ from three 30-character lines.

    Returns a dict with parsed fields and checksum validity,
    or None if the structure is clearly invalid.
    """
    if len(lines) < 3 or len(lines[0]) != 30 or len(lines[1]) != 30 or len(lines[2]) != 30:
        return None

    line1, line2, line3 = lines[0], lines[1], lines[2]

    # --- Line 1: doc type, issuing state, doc number ---
    doc_type_raw = line1[0:2].replace("<", "")
    issuing_state = line1[2:5].replace("<", "")
    doc_number_raw = line1[5:14]
    doc_number_check = line1[14]
    optional_data_1 = line1[15:30]

    # --- Line 2: DOB, sex, expiry, nationality, optional, composite ---
    dob_raw = line2[0:6]
    dob_check = line2[6]
    sex = line2[7]
    expiry_raw = line2[8:14]
    expiry_check = line2[14]
    nationality = line2[15:18].replace("<", "")
    optional_data_2 = line2[18:29]
    composite_check = line2[29]

    # --- Line 3: name ---
    name_section = line3[0:30]
    surname, given_names = _parse_mrz_name(name_section)

    # Normalize date fields
    dob_normalized = _normalize_date_field(dob_raw)
    expiry_normalized = _normalize_date_field(expiry_raw)
    doc_number = _normalize_doc_number_field(doc_number_raw)

    # --- Checksum validation ---
    checksums_ok = True

    if not _verify_check_digit(doc_number_raw, doc_number_check):
        logger.info("TD1 document number check digit failed")
        checksums_ok = False

    if not _verify_check_digit(dob_raw, dob_check):
        logger.info("TD1 DOB check digit failed")
        checksums_ok = False

    if not _verify_check_digit(expiry_raw, expiry_check):
        logger.info("TD1 expiry check digit failed")
        checksums_ok = False

    # Composite check digit: over (line1[5:30] + line2[0:7] + line2[8:15] + line2[18:29])
    composite_data = line1[5:30] + line2[0:7] + line2[8:15] + line2[18:29]
    if not _verify_check_digit(composite_data, composite_check):
        logger.info("TD1 composite check digit failed")
        checksums_ok = False

    doc_number_clean = doc_number.replace("<", "").strip()

    fields = {
        "doc_type": doc_type_raw if doc_type_raw else "I",
        "issuing_state": issuing_state,
        "name": f"{surname} {given_names}".strip(),
        "surname": surname,
        "given_names": given_names,
        "doc_number": doc_number_clean,
        "nationality": nationality,
        "dob": _format_mrz_date(dob_normalized),
        "sex": sex if sex in ("M", "F") else "",
        "expiry_date": _format_mrz_date(expiry_normalized),
    }

    return {"fields": fields, "checksum_valid": checksums_ok, "format": "TD1"}


# ─────────────────────────────────────────────
# Name Parsing
# ─────────────────────────────────────────────

def _parse_mrz_name(name_section: str) -> Tuple[str, str]:
    """
    Parse an MRZ name field into surname and given names.

    MRZ convention: SURNAME<<GIVEN<NAMES<<<...
    - '<<' separates surname from given names
    - '<' separates words within surname or given names
    - Trailing '<' is filler/padding
    """
    # Split on '<<' — first part is surname, rest is given names
    parts = name_section.split("<<", 1)
    surname = parts[0].replace("<", " ").strip()

    if len(parts) > 1:
        given_names = parts[1].replace("<", " ").strip()
    else:
        given_names = ""

    return surname, given_names


# ─────────────────────────────────────────────
# Date Formatting
# ─────────────────────────────────────────────

def _format_mrz_date(yymmdd: str) -> str:
    """
    Convert a 6-digit MRZ date (YYMMDD) to a readable date string.

    Returns format matching M3 OCR convention: YYYY-MM-DD.
    Uses a pivot year of 30: YY <= 30 → 20YY, YY > 30 → 19YY.
    Returns the raw string if it cannot be parsed.
    """
    if len(yymmdd) != 6:
        return yymmdd

    try:
        yy = int(yymmdd[0:2])
        mm = yymmdd[2:4]
        dd = yymmdd[4:6]
    except ValueError:
        return yymmdd

    # ICAO pivot: years 00-30 → 2000-2030, 31-99 → 1931-1999
    year = 2000 + yy if yy <= 30 else 1900 + yy

    return f"{year}-{mm}-{dd}"


# ─────────────────────────────────────────────
# Cross-Check Against M3 OCR
# ─────────────────────────────────────────────

def _normalize_for_comparison(value: str) -> str:
    """
    Normalize a string for fuzzy comparison between MRZ and OCR values.

    - Uppercase
    - Remove whitespace, hyphens, dots, commas, slashes
    - Remove MRZ fillers '<'
    """
    if not value:
        return ""
    result = value.upper()
    result = re.sub(r"[\s\-\.\,\/\<]", "", result)
    return result


def _dates_match(mrz_date: str, ocr_date: str) -> bool:
    """
    Compare an MRZ-parsed date (YYYY-MM-DD) against an OCR date.

    Handles common OCR date formats: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY,
    YYMMDD, and plain digit strings.
    """
    if not mrz_date or not ocr_date:
        return False

    # Normalize both to digits-only for comparison
    mrz_digits = re.sub(r"[^\d]", "", mrz_date)
    ocr_digits = re.sub(r"[^\d]", "", ocr_date)

    # Direct match on YYYYMMDD
    if mrz_digits == ocr_digits:
        return True

    # MRZ gives YYYY-MM-DD → digits = YYYYMMDD (8 digits)
    # OCR might give DD/MM/YYYY → digits = DDMMYYYY (8 digits)
    if len(mrz_digits) == 8 and len(ocr_digits) == 8:
        mrz_y, mrz_m, mrz_d = mrz_digits[0:4], mrz_digits[4:6], mrz_digits[6:8]
        # Try interpreting OCR as DDMMYYYY
        ocr_d, ocr_m, ocr_y = ocr_digits[0:2], ocr_digits[2:4], ocr_digits[4:8]
        if mrz_y == ocr_y and mrz_m == ocr_m and mrz_d == ocr_d:
            return True
        # Try interpreting OCR as YYYYMMDD (same as MRZ)
        if mrz_digits == ocr_digits:
            return True

    # OCR might give YYMMDD (6 digits) — compare against MRZ's YY portion
    if len(ocr_digits) == 6 and len(mrz_digits) == 8:
        if mrz_digits[2:8] == ocr_digits:
            return True

    return False


def _names_match(mrz_name: str, ocr_name: str) -> bool:
    """
    Compare MRZ name against OCR name with tolerance for formatting.

    MRZ names are uppercase, space-separated (after parsing).
    OCR names might have different casing, extra spaces, etc.
    """
    norm_mrz = _normalize_for_comparison(mrz_name)
    norm_ocr = _normalize_for_comparison(ocr_name)

    if not norm_mrz or not norm_ocr:
        return False

    # Exact match after normalization
    if norm_mrz == norm_ocr:
        return True

    # Check if one contains the other (OCR might have middle names MRZ omits,
    # or MRZ might have truncated names)
    if norm_mrz in norm_ocr or norm_ocr in norm_mrz:
        return True

    return False


def _cross_check(mrz_fields: Dict[str, str], ocr_fields: Dict[str, str]) -> Dict[str, bool]:
    """
    Cross-check MRZ fields against M3 OCR fields.

    Returns the required cross_check dict with boolean results.
    """
    result: Dict[str, bool] = {}

    # Name match: compare MRZ 'name' (or 'surname' + 'given_names') against OCR 'name'
    mrz_name = mrz_fields.get("name", "")
    ocr_name = ocr_fields.get("name", "")
    result["name_match"] = _names_match(mrz_name, ocr_name)

    # DOB match
    mrz_dob = mrz_fields.get("dob", "")
    ocr_dob = ocr_fields.get("dob", "")
    result["dob_match"] = _dates_match(mrz_dob, ocr_dob)

    # Document number match
    mrz_doc = _normalize_for_comparison(mrz_fields.get("doc_number", ""))
    ocr_doc = _normalize_for_comparison(ocr_fields.get("doc_number", ""))
    result["doc_number_match"] = (mrz_doc == ocr_doc) if (mrz_doc and ocr_doc) else False

    # Expiry date match
    mrz_expiry = mrz_fields.get("expiry_date", "")
    ocr_expiry = ocr_fields.get("expiry_date", "")
    result["expiry_match"] = _dates_match(mrz_expiry, ocr_expiry)

    return result


# ─────────────────────────────────────────────
# Fallback: Extract MRZ from M3 raw_text
# ─────────────────────────────────────────────

def _try_extract_mrz_from_raw_text(raw_text: str) -> Optional[List[str]]:
    """
    Attempt to find MRZ lines in M3's raw OCR text as a fallback
    when image-based detection fails.

    This is less reliable than dedicated MRZ OCR but provides
    a safety net.
    """
    return _extract_mrz_lines_from_text(raw_text)


# ─────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────

def run(ingestion_out: IngestionOutput, ocr_out: OCROutput) -> MRZOutput:
    """
    M4 — MRZ Parser + Cross-Check.

    1. Detect and crop the MRZ zone from the document image (OpenCV).
    2. Run a dedicated OCR pass on the MRZ crop (Tesseract).
    3. Extract and validate MRZ lines.
    4. Parse per ICAO Doc 9303 (TD3 passport or TD1 ID card).
    5. Validate all check digits.
    6. Cross-check MRZ fields against M3 OCR fields.
    7. Return MRZOutput.

    Gracefully handles missing/invalid MRZ by returning mrz_present=False.
    """
    # Default fallback result — no MRZ
    no_mrz_result = MRZOutput(
        mrz_present=False,
        mrz_fields={},
        checksum_valid=False,
        cross_check={
            "name_match": False,
            "dob_match": False,
            "doc_number_match": False,
            "expiry_match": False,
        },
    )

    # ── Step 1: Attempt image-based MRZ detection ──
    mrz_lines: Optional[List[str]] = None
    image_path = ingestion_out.doc_image_path

    if image_path and os.path.isfile(image_path):
        try:
            mrz_crop = _detect_mrz_region(image_path)
            if mrz_crop is not None:
                # Step 2: Dedicated OCR on the MRZ crop
                mrz_raw_text = _ocr_mrz_region(mrz_crop)
                mrz_lines = _extract_mrz_lines_from_text(mrz_raw_text)
                if mrz_lines:
                    logger.info("MRZ detected via image-based detection (%d lines)", len(mrz_lines))
        except Exception as e:
            logger.warning("Image-based MRZ detection failed: %s", e)

    # ── Fallback: try extracting MRZ from M3's raw_text ──
    if mrz_lines is None:
        mrz_lines = _try_extract_mrz_from_raw_text(ocr_out.raw_text)
        if mrz_lines:
            logger.info("MRZ detected via fallback from M3 raw_text (%d lines)", len(mrz_lines))

    # ── No MRZ found ──
    if mrz_lines is None:
        logger.info("No MRZ detected in document")
        return no_mrz_result

    # ── Step 3: Parse MRZ based on format ──
    parsed: Optional[Dict] = None

    if len(mrz_lines) == 2:
        # Try TD3 (passport: 2 lines × 44 chars)
        parsed = _parse_td3(mrz_lines)
    elif len(mrz_lines) == 3:
        # Try TD1 (ID card: 3 lines × 30 chars)
        parsed = _parse_td1(mrz_lines)

    if parsed is None:
        logger.info("MRZ lines found but could not be parsed (format mismatch)")
        return no_mrz_result

    # ── Step 4: Build cross-check against M3 OCR ──
    mrz_fields = parsed["fields"]
    cross_check_result = _cross_check(mrz_fields, ocr_out.fields)

    # ── Step 5: Return MRZOutput ──
    return MRZOutput(
        mrz_present=True,
        mrz_fields=mrz_fields,
        checksum_valid=parsed["checksum_valid"],
        cross_check=cross_check_result,
    )
