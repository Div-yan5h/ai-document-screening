"""
M5 — Rule Validation
====================
Validates document information for logical and structural validity.
Consumes outputs from M3 (OCR) and M4 (MRZ Parser + Cross-Check).

Performs:
  1. MRZ Preference & Field Selection (prefers valid MRZ over OCR)
  2. Expiry Validation (expiry_date < today)
  3. Format Validation (doc_number format, date structure)
  4. Logical Consistency Validation (issue_date < expiry_date, issue_date not future,
     issue_date >= dob, plausible DOB age range)
  5. Human-Readable Flag Generation (plain-English sentences for officer review)

Owner: P3
Dependencies: standard library (datetime, re, logging, typing) + frozen contracts
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import List, Optional

from backend.app.schemas.contracts import MRZOutput, OCROutput, RuleValidationOutput

logger = logging.getLogger(__name__)

# Supported date formats for parsing M3 OCR and M4 MRZ dates
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%d %b %Y",
    "%d-%b-%Y",
    "%d %B %Y",
    "%d-%B-%Y",
    "%Y%m%d",
)


def _parse_date(date_str: Optional[str]) -> Optional[datetime.date]:
    """
    Parse a date string into a datetime.date object.

    Handles ISO, European, slash/dot/hyphen-delimited, named month,
    and 6-digit YYMMDD formats.
    Returns None if date_str is missing, empty, or cannot be parsed.
    """
    if not date_str or not isinstance(date_str, str):
        return None

    cleaned = date_str.strip()
    if not cleaned:
        return None

    for fmt in _DATE_FORMATS:
        try:
            return datetime.datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue

    # Handle 6-digit MRZ YYMMDD format
    if len(cleaned) == 6 and cleaned.isdigit():
        try:
            yy = int(cleaned[:2])
            mm = int(cleaned[2:4])
            dd = int(cleaned[4:6])
            # ICAO pivot: YY <= 35 -> 20YY, YY > 35 -> 19YY
            year = 2000 + yy if yy <= 35 else 1900 + yy
            return datetime.date(year, mm, dd)
        except ValueError:
            pass

    return None


def _calculate_age(dob: datetime.date, today: datetime.date) -> int:
    """Calculate age in complete years relative to the given reference date."""
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _is_valid_doc_number(doc_number: str, doc_type: Optional[str] = None) -> bool:
    """
    Validate document number structure.

    Checks:
      - Length between 5 and 20 characters
      - Alphanumeric with optional single internal hyphens
      - At least 4 alphanumeric characters
      - No OCR noise/garbage symbols
    """
    if not doc_number or not isinstance(doc_number, str):
        return False

    clean = doc_number.strip().replace(" ", "")
    if len(clean) < 5 or len(clean) > 20:
        return False

    # Alphanumeric with optional hyphens (no leading/trailing hyphens)
    if not re.match(r"^[A-Za-z0-9]+(-[A-Za-z0-9]+)*$", clean):
        return False

    alnum_count = sum(1 for c in clean if c.isalnum())
    if alnum_count < 4:
        return False

    return True


def run(ocr_out: OCROutput, mrz_out: MRZOutput) -> RuleValidationOutput:
    """
    M5 — Rule Validation Entry Point.

    Validates document rules against OCR and MRZ inputs:
      1. Prefers MRZ fields when MRZ is present and checksum is valid.
      2. Validates document expiry against today's date at runtime.
      3. Validates document number format and date field readability.
      4. Validates date logic (issue date vs expiry date, issue date in future, DOB plausibility).
      5. Generates human-readable flags for any validation failures.
    """
    flags: List[str] = []
    format_valid = True
    logic_valid = True
    is_expired = False
    today = datetime.date.today()

    # ── Step 1: Field selection (MRZ preference when checksum is valid) ──
    use_mrz = bool(mrz_out and mrz_out.mrz_present and mrz_out.checksum_valid)
    mrz_fields = mrz_out.mrz_fields if (use_mrz and mrz_out.mrz_fields) else {}
    ocr_fields = ocr_out.fields if (ocr_out and ocr_out.fields) else {}

    def _get_field(key: str) -> Optional[str]:
        val = mrz_fields.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
        val = ocr_fields.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
        return None

    raw_doc_number = _get_field("doc_number")
    raw_expiry_date = _get_field("expiry_date")
    raw_dob = _get_field("dob")
    raw_issue_date = _get_field("issue_date")
    doc_type = _get_field("doc_type") or ocr_fields.get("doc_type", "")

    # ── Step 2: Document Number Format Validation ──
    if not raw_doc_number:
        format_valid = False
        flags.append("The document number could not be identified.")
    elif not _is_valid_doc_number(raw_doc_number, doc_type):
        format_valid = False
        flags.append("The document number does not match the expected format.")

    # ── Step 3: Expiry Date Validation ──
    expiry_dt: Optional[datetime.date] = None
    if not raw_expiry_date:
        format_valid = False
        flags.append("The document expiry date could not be identified.")
    else:
        expiry_dt = _parse_date(raw_expiry_date)
        if expiry_dt is None:
            format_valid = False
            flags.append("The document expiry date could not be validated.")
        else:
            if expiry_dt < today:
                is_expired = True
                flags.append("The document has expired.")
            else:
                is_expired = False

    # ── Step 4: Date of Birth Validation ──
    dob_dt: Optional[datetime.date] = None
    if not raw_dob:
        format_valid = False
        flags.append("The date of birth could not be identified.")
    else:
        dob_dt = _parse_date(raw_dob)
        if dob_dt is None:
            format_valid = False
            flags.append("The date of birth could not be validated.")
        else:
            age = _calculate_age(dob_dt, today)
            if age < 0 or age > 120:
                logic_valid = False
                flags.append("The date of birth is not plausible.")

    # ── Step 5: Issue Date & Logical Consistency Validation ──
    issue_dt: Optional[datetime.date] = None
    if raw_issue_date:
        issue_dt = _parse_date(raw_issue_date)
        if issue_dt is None:
            format_valid = False
            flags.append("The document issue date could not be validated.")
        else:
            if issue_dt > today:
                logic_valid = False
                flags.append("The document issue date cannot be in the future.")
            if dob_dt and issue_dt < dob_dt:
                logic_valid = False
                flags.append("The document issue date cannot be earlier than the date of birth.")
            if expiry_dt and issue_dt >= expiry_dt:
                logic_valid = False
                flags.append("The issue date is not earlier than the expiry date.")

    return RuleValidationOutput(
        is_expired=is_expired,
        format_valid=format_valid,
        logic_valid=logic_valid,
        flags=flags,
    )

