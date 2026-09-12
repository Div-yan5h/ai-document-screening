r"""
M3 — Document Field Extractor
=============================
Converts PaddleOCR text detections and recognition scores into the six
contract-mandated fields: name, dob, doc_number, expiry_date, nationality,
issue_date.

Architecture & Guarantees:
- doc_type (from M2 ClassifierOutput) controls field-selection priority.
- Tolerates OCR formatting noise INSIDE known labels (e.g. VISANUMBER, DATE OFISSUE).
- Shared, universal boundary-safety mechanism for ALL fields:
  1. Label Anchor Requirement: Every field must be anchored to a recognized label.
  2. Label-Value Separator Requirement: On same line, requires at least one
     explicit delimiter [:;\.\\s\\-\\|]+.
  3. Trailing Boundary Requirement: Candidate values must cleanly terminate
     without fusing directly into subsequent labels or tokens.
  4. Fused Label-Collision Rejection: Any token containing a label fused directly
     to a preceding character ([A-Za-z0-9] + LABEL) is strictly rejected.

Owner: P2
"""

import re
from typing import Any, Callable, Dict, List, Optional, Tuple

REQUIRED_FIELDS: Tuple[str, ...] = (
    "name",
    "dob",
    "doc_number",
    "expiry_date",
    "nationality",
    "issue_date",
)

# Standard date patterns with non-word / non-digit boundaries
DATE_REGEXES = [
    # DD/MM/YYYY or DD-MM-YYYY or DD.MM.YYYY
    re.compile(r"(?:^|[^\d])(\d{1,2}[-/. ]\d{1,2}[-/. ]\d{4})(?:[^\d]|$)"),
    # YYYY/MM/DD or YYYY-MM-DD or YYYY.MM.DD
    re.compile(r"(?:^|[^\d])(\d{4}[-/. ]\d{1,2}[-/. ]\d{1,2})(?:[^\d]|$)"),
    # DD MMM YYYY (e.g. 15 MAY 1990)
    re.compile(r"(?:^|[^\d])(\d{1,2}[-/. ](?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*[-/. ]\d{4})(?:[^\d]|$)", re.IGNORECASE),
    # DDMMMYYYY (e.g. 15MAY1990)
    re.compile(r"(?:^|[^\d])(\d{1,2}(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\d{4})(?:[^\d]|$)", re.IGNORECASE),
]

# Field-specific label patterns (tolerant of OCR whitespace variations inside the label)
DOB_KW_PATTERNS = [r"DATE\s*OF\s*BIRTH", r"DOB", r"BIRTH\s*DATE", r"BORN", r"BIRTH"]
EXPIRY_KW_PATTERNS = [r"DATE\s*OF\s*EXPIRY", r"EXPIRY\s*DATE", r"EXPIRATION\s*DATE", r"EXP\s*DATE", r"VALID\s*UNTIL", r"EXPIRY", r"EXPIRES", r"VALID\s*THRU"]
ISSUE_KW_PATTERNS = [r"DATE\s*OF\s*ISSUE", r"ISSUE\s*DATE", r"ISSUED\s*ON", r"ISSUED", r"VALID\s*FROM"]

PASSPORT_NUM_PATTERNS = [r"PASSPORT\s*NUMBER", r"PASSPORT\s*NO", r"PASSPORT", r"DOCUMENT\s*NO", r"DOC\s*NO"]
IDCARD_NUM_PATTERNS = [r"IDENTITY\s*CARD\s*NO", r"ID\s*CARD\s*NO", r"ID\s*NUMBER", r"NATIONAL\s*ID", r"IDENTITY\s*NO", r"CARD\s*NO", r"ID\s*NO", r"DOCUMENT\s*NO", r"DOC\s*NO"]
VISA_NUM_PATTERNS = [r"VISA\s*NUMBER", r"VISA\s*NO", r"CONTROL\s*NO", r"VISA", r"DOCUMENT\s*NO", r"DOC\s*NO"]
GENERIC_NUM_PATTERNS = [r"DOCUMENT\s*NO", r"DOC\s*NO", r"ID\s*NO", r"NUMBER", r"NO"]

NATIONALITY_KW_PATTERNS = [r"NATIONALITY", r"CITIZENSHIP", r"COUNTRY\s*CODE", r"CITIZEN"]

SURNAME_KW_PATTERNS = [r"SURNAME", r"LAST\s*NAME", r"NOM"]
GIVEN_NAME_KW_PATTERNS = [r"GIVEN\s*NAMES?", r"FIRST\s*NAMES?", r"PRENOMS?"]
FULL_NAME_KW_PATTERNS = [r"FULL\s*NAME", r"NAME", r"BEARER", r"CARDHOLDER"]

# Comprehensive registry of all known document labels used for universal collision detection
ALL_DOCUMENT_LABEL_PATTERNS = sorted(
    list(set(
        DOB_KW_PATTERNS + EXPIRY_KW_PATTERNS + ISSUE_KW_PATTERNS +
        PASSPORT_NUM_PATTERNS + IDCARD_NUM_PATTERNS + VISA_NUM_PATTERNS + GENERIC_NUM_PATTERNS +
        NATIONALITY_KW_PATTERNS + SURNAME_KW_PATTERNS + GIVEN_NAME_KW_PATTERNS + FULL_NAME_KW_PATTERNS
    )),
    key=len,
    reverse=True,
)


class FieldExtractor:
    """
    Extracts structured fields from OCR regions based on document type.
    Enforces a single, shared boundary-safety mechanism for all fields.
    """

    def __init__(self):
        self.required_fields = REQUIRED_FIELDS

    def extract(
        self,
        regions: List[Dict[str, Any]],
        doc_type: str,
    ) -> Tuple[Dict[str, str], Dict[str, float]]:
        """
        Extracts fields and confidence scores from OCR regions.

        Args:
            regions: List of dicts with keys 'text' (str) and 'score' (float).
            doc_type: Classified document type ('passport', 'id_card', 'visa', 'unknown').

        Returns:
            Tuple of (fields, field_confidences) conforming to OCROutput.
        """
        fields: Dict[str, str] = {f: "" for f in self.required_fields}
        field_confidences: Dict[str, float] = {f: 0.0 for f in self.required_fields}

        if not regions:
            return fields, field_confidences

        clean_doc_type = (doc_type or "unknown").lower()

        if clean_doc_type == "passport":
            self._extract_passport(regions, fields, field_confidences)
        elif clean_doc_type == "id_card":
            self._extract_id_card(regions, fields, field_confidences)
        elif clean_doc_type == "visa":
            self._extract_visa(regions, fields, field_confidences)
        else:
            self._extract_unknown(regions, fields, field_confidences)

        return fields, field_confidences

    # -------------------------------------------------------------------------
    # Shared Universal Boundary-Safety Engine
    # -------------------------------------------------------------------------

    @staticmethod
    def _has_fused_label_collision(text: str) -> bool:
        """
        General boundary check: detects if any known document label is fused
        directly onto a preceding alphanumeric character without a delimiter.
        e.g. 'DOEGIVEN', 'SMITHFULLNAME', 'X8912345EXPIRY'.
        """
        all_kw_regex = "|".join([f"(?:{kw})" for kw in ALL_DOCUMENT_LABEL_PATTERNS])
        # A word character immediately followed by a known label indicates a fused boundary
        return bool(re.search(rf"[A-Za-z0-9](?:{all_kw_regex})", text.upper()))

    @classmethod
    def _extract_anchored_field(
        cls,
        regions: List[Dict[str, Any]],
        label_patterns: List[str],
        value_parser_fn: Callable[[str], Optional[Tuple[str, int]]],
        validator_fn: Callable[[str], bool],
    ) -> Tuple[str, float]:
        """
        SHARED UNIVERSAL BOUNDARY FUNCTION
        ==================================
        Extracts a field value anchored to one of label_patterns.
        Guarantees:
        1. Anchor Isolation: Label must not be fused to a preceding alphanumeric token.
        2. Separator Requirement (Same Line): Must have at least one explicit delimiter
           [:;\\.\\s\\-\\|]+ between label and value.
        3. Trailing Boundary Requirement: Extracted value must not fuse into subsequent
           alphanumeric characters.
        4. Fused Label Collision: Rejects if the candidate token fuses with any known label.
        5. Clean Next-Line Termination: If value is on next line, current line must terminate.
        """
        kw_pattern = "|".join([f"(?:{kw})" for kw in sorted(label_patterns, key=len, reverse=True)])

        for i, reg in enumerate(regions):
            text = reg["text"].strip()
            score = float(reg["score"])
            upper = text.upper()

            # Find label anchor
            m_lbl = re.search(rf"(?:{kw_pattern})", upper)
            if not m_lbl:
                continue

            lbl_start, lbl_end = m_lbl.span()

            # 1. Anchor Isolation: label must not be a fused suffix of another word
            if lbl_start > 0 and upper[lbl_start - 1].isalnum():
                continue

            trailing_text = upper[lbl_end:]

            # Case A: Value on NEXT line (current line terminates cleanly after label)
            if re.match(r"^[:;\.\s\-\|]*$", trailing_text) and i + 1 < len(regions):
                next_text = regions[i + 1]["text"].strip()
                next_score = float(regions[i + 1]["score"])
                next_upper = next_text.upper()

                # Parse candidate from next line
                res = value_parser_fn(next_upper)
                if res:
                    candidate, _ = res
                    if validator_fn(candidate) and not cls._has_fused_label_collision(next_upper):
                        return candidate, round(next_score, 4)

            # Case B: Value on SAME line
            # 2. Separator Requirement: must have at least one delimiter after label
            sep_match = re.match(r"^[:;\.\s\-\|]+", trailing_text)
            if not sep_match:
                # Label is fused directly to following characters (e.g. NATIONALITYUTO, DOCNOX8912345)
                continue

            after_sep = trailing_text[sep_match.end():]
            if not after_sep:
                continue

            # Check for fused label collisions in the remainder of the line
            if cls._has_fused_label_collision(after_sep):
                # Ambiguous collision (e.g. 'SMITHFULLNAME', 'DOEGIVEN', 'X8912345EXPIRY') -> reject
                continue

            # Parse candidate value
            res = value_parser_fn(after_sep)
            if not res:
                continue

            candidate, cand_len = res

            # 3. Trailing Boundary Requirement: candidate must cleanly terminate
            remainder = after_sep[cand_len:]
            if remainder and re.match(r"^[A-Za-z0-9]", remainder):
                # Candidate directly touches alphanumeric character -> fused, reject
                continue

            if validator_fn(candidate):
                return candidate, round(score, 4)

        return "", 0.0

    # -------------------------------------------------------------------------
    # Value Parsers for Shared Engine
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_name_val(s: str) -> Optional[Tuple[str, int]]:
        """Parses an alphabetic name (single or multi-word) up to the next known label or end of line."""
        all_kw = "|".join([f"(?:{kw})" for kw in ALL_DOCUMENT_LABEL_PATTERNS])
        # Matches name tokens until reaching another document label or line boundary
        m = re.match(rf"^([A-Z\s\-]+?)(?=(?:\s*[:;\.\-\|]+\s*(?:{all_kw})\b|\s+(?:{all_kw})\b|$))", s)
        if m:
            val = m.group(1).strip()
            if val:
                return val, m.end(1)
        return None

    @staticmethod
    def _parse_doc_num_val(s: str) -> Optional[Tuple[str, int]]:
        """Parses an alphanumeric document number."""
        m = re.match(r"^([A-Z0-9<-]{5,20})", s)
        if m:
            val = m.group(1).strip()
            return val, m.end(1)
        return None

    @staticmethod
    def _parse_nationality_val(s: str) -> Optional[Tuple[str, int]]:
        """Parses a nationality or country code."""
        m = re.match(r"^([A-Z]{3,20})", s)
        if m:
            val = m.group(1).strip()
            return val, m.end(1)
        return None

    @staticmethod
    def _parse_date_val(s: str) -> Optional[Tuple[str, int]]:
        """Parses standard date format matching DATE_REGEXES."""
        for regex in DATE_REGEXES:
            m = regex.search(s)
            if m and m.start(1) == 0:  # Must be anchored at start of value
                val = m.group(1).strip()
                return val, m.end(1)
        # Also allow unanchored date if preceded only by whitespace
        for regex in DATE_REGEXES:
            m = regex.search(s)
            if m:
                val = m.group(1).strip()
                return val, m.end(1)
        return None

    # -------------------------------------------------------------------------
    # Document-Specific Extraction Pipelines
    # -------------------------------------------------------------------------

    def _extract_passport(
        self,
        regions: List[Dict[str, Any]],
        fields: Dict[str, str],
        confidences: Dict[str, float],
    ) -> None:
        self._extract_passport_name(regions, fields, confidences)
        val, conf = self._extract_anchored_field(
            regions, PASSPORT_NUM_PATTERNS, self._parse_doc_num_val, lambda v: self._is_valid_doc_num(v, "passport")
        )
        fields["doc_number"], confidences["doc_number"] = val, conf

        val, conf = self._extract_anchored_field(
            regions, NATIONALITY_KW_PATTERNS, self._parse_nationality_val, self._is_valid_nationality
        )
        fields["nationality"], confidences["nationality"] = val, conf

        self._extract_all_dates(regions, fields, confidences)

    def _extract_id_card(
        self,
        regions: List[Dict[str, Any]],
        fields: Dict[str, str],
        confidences: Dict[str, float],
    ) -> None:
        self._extract_id_name(regions, fields, confidences)
        val, conf = self._extract_anchored_field(
            regions, IDCARD_NUM_PATTERNS, self._parse_doc_num_val, lambda v: self._is_valid_doc_num(v, "id_card")
        )
        fields["doc_number"], confidences["doc_number"] = val, conf

        val, conf = self._extract_anchored_field(
            regions, NATIONALITY_KW_PATTERNS, self._parse_nationality_val, self._is_valid_nationality
        )
        fields["nationality"], confidences["nationality"] = val, conf

        self._extract_all_dates(regions, fields, confidences)

    def _extract_visa(
        self,
        regions: List[Dict[str, Any]],
        fields: Dict[str, str],
        confidences: Dict[str, float],
    ) -> None:
        self._extract_visa_name(regions, fields, confidences)
        val, conf = self._extract_anchored_field(
            regions, VISA_NUM_PATTERNS, self._parse_doc_num_val, lambda v: self._is_valid_doc_num(v, "visa")
        )
        fields["doc_number"], confidences["doc_number"] = val, conf

        val, conf = self._extract_anchored_field(
            regions, NATIONALITY_KW_PATTERNS, self._parse_nationality_val, self._is_valid_nationality
        )
        fields["nationality"], confidences["nationality"] = val, conf

        self._extract_all_dates(regions, fields, confidences)

    def _extract_unknown(
        self,
        regions: List[Dict[str, Any]],
        fields: Dict[str, str],
        confidences: Dict[str, float],
    ) -> None:
        val, conf = self._extract_anchored_field(
            regions, FULL_NAME_KW_PATTERNS, self._parse_name_val, self._is_valid_name_token
        )
        fields["name"], confidences["name"] = val, conf

        val, conf = self._extract_anchored_field(
            regions, GENERIC_NUM_PATTERNS, self._parse_doc_num_val, lambda v: self._is_valid_doc_num(v, "unknown")
        )
        fields["doc_number"], confidences["doc_number"] = val, conf

        val, conf = self._extract_anchored_field(
            regions, NATIONALITY_KW_PATTERNS, self._parse_nationality_val, self._is_valid_nationality
        )
        fields["nationality"], confidences["nationality"] = val, conf

        self._extract_all_dates(regions, fields, confidences)

    # -------------------------------------------------------------------------
    # Field-Specific Wrappers Calling Shared Engine
    # -------------------------------------------------------------------------

    def _extract_passport_name(
        self,
        regions: List[Dict[str, Any]],
        fields: Dict[str, str],
        confidences: Dict[str, float],
    ) -> None:
        """Extracts surname + given names using the shared anchored boundary engine."""
        sur_val, sur_conf = self._extract_anchored_field(
            regions, SURNAME_KW_PATTERNS, self._parse_name_val, self._is_valid_name_token
        )
        giv_val, giv_conf = self._extract_anchored_field(
            regions, GIVEN_NAME_KW_PATTERNS, self._parse_name_val, self._is_valid_name_token
        )

        if sur_val and giv_val:
            fields["name"] = f"{sur_val} {giv_val}"
            confidences["name"] = round((sur_conf + giv_conf) / 2.0, 4)
        elif sur_val:
            fields["name"] = sur_val
            confidences["name"] = sur_conf
        elif giv_val:
            fields["name"] = giv_val
            confidences["name"] = giv_conf
        else:
            # Fallback to single FULL NAME anchor
            fn_val, fn_conf = self._extract_anchored_field(
                regions, FULL_NAME_KW_PATTERNS, self._parse_name_val, self._is_valid_name_token
            )
            fields["name"], confidences["name"] = fn_val, fn_conf

    def _extract_id_name(
        self,
        regions: List[Dict[str, Any]],
        fields: Dict[str, str],
        confidences: Dict[str, float],
    ) -> None:
        fn_val, fn_conf = self._extract_anchored_field(
            regions, FULL_NAME_KW_PATTERNS, self._parse_name_val, self._is_valid_name_token
        )
        if fn_val:
            fields["name"], confidences["name"] = fn_val, fn_conf
        else:
            self._extract_passport_name(regions, fields, confidences)

    def _extract_visa_name(
        self,
        regions: List[Dict[str, Any]],
        fields: Dict[str, str],
        confidences: Dict[str, float],
    ) -> None:
        fn_val, fn_conf = self._extract_anchored_field(
            regions, FULL_NAME_KW_PATTERNS, self._parse_name_val, self._is_valid_name_token
        )
        if fn_val:
            fields["name"], confidences["name"] = fn_val, fn_conf
        else:
            self._extract_passport_name(regions, fields, confidences)

    def _extract_all_dates(
        self,
        regions: List[Dict[str, Any]],
        fields: Dict[str, str],
        confidences: Dict[str, float],
    ) -> None:
        """Extracts dob, expiry_date, and issue_date using the shared anchored boundary engine."""
        if not fields["dob"]:
            val, conf = self._extract_anchored_field(
                regions, DOB_KW_PATTERNS, self._parse_date_val, self._is_valid_date
            )
            fields["dob"], confidences["dob"] = val, conf

        if not fields["expiry_date"]:
            val, conf = self._extract_anchored_field(
                regions, EXPIRY_KW_PATTERNS, self._parse_date_val, self._is_valid_date
            )
            fields["expiry_date"], confidences["expiry_date"] = val, conf

        if not fields["issue_date"]:
            val, conf = self._extract_anchored_field(
                regions, ISSUE_KW_PATTERNS, self._parse_date_val, self._is_valid_date
            )
            fields["issue_date"], confidences["issue_date"] = val, conf

    # -------------------------------------------------------------------------
    # Shared Validation Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _is_valid_name_token(token: str) -> bool:
        upper = token.upper().strip()
        if not upper or len(upper) < 2:
            return False
        if any(exc in upper for exc in ["PASSPORT", "IDENTITY", "CARD", "VISA", "DATE", "BIRTH", "EXPIRY", "ISSUE"]):
            return False
        return bool(re.match(r"^[A-Z\s\-]+$", upper))

    @staticmethod
    def _is_valid_doc_num(token: str, doc_type: str) -> bool:
        upper = token.strip().upper()
        if len(upper) < 5 or len(upper) > 20:
            return False
        if not any(char.isdigit() for char in upper):
            return False
        if any(w in upper for w in ["PASSPORT", "IDENTITY", "DOCUMENT", "NUMBER", "EXPIRY", "BIRTH", "ISSUE"]):
            return False
        return bool(re.match(r"^[A-Z0-9<\-]+$", upper))

    @staticmethod
    def _is_valid_nationality(token: str) -> bool:
        upper = token.strip().upper()
        if len(upper) < 3 or len(upper) > 20:
            return False
        if any(kw in upper for kw in ["DATE", "BIRTH", "EXPIRY", "PASSPORT", "CARD", "ISSUE"]):
            return False
        return bool(re.match(r"^[A-Z]+$", upper))

    @staticmethod
    def _is_valid_date(token: str) -> bool:
        return bool(token.strip())
