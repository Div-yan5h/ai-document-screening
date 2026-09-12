"""
M8 — Database / Blacklist Check Service
=======================================
Implements business logic for querying synthetic screening records in MongoDB.
Answers: "Does this document number exist in our records, and if so, what is its status?"

Supported statuses:
- clean
- blacklisted
- watchlist
- not_found
- db_unavailable

Safety Rules:
1. Absence of a record returns "not_found", NEVER "clean".
2. Database / connectivity failure returns "db_unavailable", NEVER "clean".
3. Unexpected or corrupted status in database fails safely as "db_unavailable".
4. Document number selection prefers valid MRZ over OCR.

Owner: P4 (Identity & Records)
"""

import logging
from typing import Any, Dict, Optional, Set

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from backend.app.modules.m8_db.connection import get_blacklist_collection
from backend.app.schemas.contracts import DBCheckOutput, MRZOutput, OCROutput

logger = logging.getLogger(__name__)

# Allowed statuses from stored records
VALID_STATUSES: Set[str] = {"clean", "blacklisted", "watchlist"}

# Candidate field names for document number in MRZ and OCR outputs
DOC_NUMBER_KEYS = (
    "document_number",
    "doc_number",
    "document_no",
    "passport_number",
    "id_number",
)


def normalize_document_number(raw_doc_number: Optional[Any]) -> Optional[str]:
    """
    Normalize a raw document number string.

    Rules:
    - Convert to string
    - Strip surrounding whitespace
    - Convert to uppercase
    - Reject empty values (return None)
    """
    if raw_doc_number is None:
        return None

    cleaned = str(raw_doc_number).strip().upper()
    return cleaned if cleaned else None


def extract_doc_number_from_mapping(mapping: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Search a dictionary for a usable document number using recognized key variants.
    Handles exact matches first, then falls back to case-insensitive lookup.
    """
    if not mapping or not isinstance(mapping, dict):
        return None

    # 1. Exact key match
    for key in DOC_NUMBER_KEYS:
        if key in mapping:
            normalized = normalize_document_number(mapping[key])
            if normalized:
                return normalized

    # 2. Case-insensitive key match
    lowered_keys = {str(k).strip().lower(): v for k, v in mapping.items()}
    for key in DOC_NUMBER_KEYS:
        if key in lowered_keys:
            normalized = normalize_document_number(lowered_keys[key])
            if normalized:
                return normalized

    return None


def select_document_number(
    mrz_out: Optional[MRZOutput],
    ocr_out: Optional[OCROutput],
) -> Optional[str]:
    """
    Select and normalize document number according to M8 priority rules:

    1. Prefer MRZ document number IF:
       - mrz_out.checksum_valid is True
       - and a usable document number exists in mrz_out.mrz_fields
    2. Otherwise fall back to OCR document number from ocr_out.fields
    3. If neither provides a usable document number, return None
    """
    # Priority 1: MRZ (only if checksum is valid)
    if mrz_out is not None and getattr(mrz_out, "checksum_valid", False):
        mrz_fields = getattr(mrz_out, "mrz_fields", None)
        doc_num = extract_doc_number_from_mapping(mrz_fields)
        if doc_num:
            return doc_num

    # Priority 2: OCR fallback
    if ocr_out is not None:
        ocr_fields = getattr(ocr_out, "fields", None)
        doc_num = extract_doc_number_from_mapping(ocr_fields)
        if doc_num:
            return doc_num

    return None


def lookup_record(
    doc_number: str,
    collection: Optional[Collection] = None,
) -> DBCheckOutput:
    """
    Query MongoDB collection by normalized doc_number.

    Safety Guarantees:
    - Record not found -> status="not_found", record_meta=None (NEVER "clean")
    - Database failure -> status="db_unavailable", record_meta=None (NEVER "clean")
    - Unexpected status -> status="db_unavailable", record_meta=None (fails safely)
    - Successful query -> status and record_meta from record (excluding MongoDB internal _id)
    """
    try:
        target_collection = (
            collection if collection is not None else get_blacklist_collection()
        )
        record = target_collection.find_one(
            {"doc_number": doc_number},
            {"_id": 0},
        )

        if record is None:
            return DBCheckOutput(status="not_found", record_meta=None)

        stored_status = record.get("status")
        if stored_status not in VALID_STATUSES:
            logger.warning(
                "Unexpected status '%s' in database record for doc_number '%s'. Failing safely.",
                stored_status,
                doc_number,
            )
            return DBCheckOutput(status="db_unavailable", record_meta=None)

        record_meta = record.get("record_meta")
        if record_meta is not None and not isinstance(record_meta, dict):
            record_meta = {"raw_meta": record_meta}

        return DBCheckOutput(status=stored_status, record_meta=record_meta)

    except PyMongoError as err:
        logger.error("MongoDB error during document lookup: %s", err)
        return DBCheckOutput(status="db_unavailable", record_meta=None)
    except Exception as err:
        logger.error("Unexpected error during document lookup: %s", err)
        return DBCheckOutput(status="db_unavailable", record_meta=None)


def check_database(
    mrz_out: MRZOutput,
    ocr_out: OCROutput,
    collection: Optional[Collection] = None,
) -> DBCheckOutput:
    """
    Primary M8 service function.

    Takes MRZOutput and OCROutput, resolves the appropriate document number,
    queries MongoDB, and returns the DBCheckOutput contract.

    Args:
        mrz_out: Output from M4 MRZ parser.
        ocr_out: Output from M3 OCR extractor.
        collection: Optional PyMongo collection (defaults to connection.py collection).

    Returns:
        DBCheckOutput with status in ("clean", "blacklisted", "watchlist", "not_found", "db_unavailable").
    """
    doc_number = select_document_number(mrz_out, ocr_out)

    if not doc_number:
        return DBCheckOutput(status="not_found", record_meta=None)

    return lookup_record(doc_number, collection=collection)
