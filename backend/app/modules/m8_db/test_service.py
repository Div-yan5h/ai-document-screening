"""
M8 — Database / Blacklist Check Service Tests
=============================================
Unit tests for the M8 service layer (service.py).
Exercises document number selection, normalization, database lookup,
and safety guarantees (absence -> not_found, db error -> db_unavailable).

Tested independently of a live MongoDB instance using lightweight fake collections.

Usage:
    pytest backend/app/modules/m8_db/test_service.py
    # or directly:
    python3 -m backend.app.modules.m8_db.test_service

Owner: P4 (Identity & Records)
"""

import sys
from typing import Any, Dict, List, Optional

from pymongo.errors import PyMongoError

# Gracefully provide a lightweight mock BaseModel if pydantic is not yet installed
# in the execution environment so contracts.py can load without error.
try:
    import pydantic  # noqa: F401
except ImportError:
    from unittest.mock import MagicMock

    class MockBaseModel:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

        def __repr__(self):
            return f"{self.__class__.__name__}({self.__dict__})"

    mock_pydantic = MagicMock()
    mock_pydantic.BaseModel = MockBaseModel
    sys.modules["pydantic"] = mock_pydantic

from backend.app.modules.m8_db.seed_data import SEED_RECORDS
from backend.app.modules.m8_db.service import check_database
from backend.app.schemas.contracts import DBCheckOutput, MRZOutput, OCROutput


# =============================================================================
# Fake Collections for In-Memory Testing
# =============================================================================

class FakeMongoCollection:
    """
    In-memory fake MongoDB collection pre-loaded with synthetic seed records.
    Implements minimal find_one() for service testing without a live MongoDB daemon.
    """

    def __init__(self, records: Optional[List[Dict[str, Any]]] = None):
        self.records_by_doc: Dict[str, Dict[str, Any]] = {}
        self.call_count: int = 0
        self.last_query: Optional[Dict[str, Any]] = None

        dataset = records if records is not None else SEED_RECORDS
        for rec in dataset:
            doc_no = rec.get("doc_number")
            if doc_no:
                self.records_by_doc[doc_no] = dict(rec)

    def find_one(
        self,
        query: Dict[str, Any],
        projection: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        self.call_count += 1
        self.last_query = query
        doc_no = query.get("doc_number")
        record = self.records_by_doc.get(doc_no)
        if record is None:
            return None

        result = dict(record)
        if projection and projection.get("_id") == 0:
            result.pop("_id", None)
        return result


class FailingMongoCollection:
    """
    Fake collection that always raises PyMongoError on find_one()
    to simulate database and network connectivity failures.
    """

    def __init__(self, error_message: str = "Simulated MongoDB connection lost"):
        self.error_message = error_message
        self.call_count: int = 0

    def find_one(
        self,
        query: Dict[str, Any],
        projection: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        self.call_count += 1
        raise PyMongoError(self.error_message)


# =============================================================================
# Test Cases
# =============================================================================

def test_clean_record_returns_clean() -> None:
    """
    Case 1: Clean Record.
    Given a valid MRZ document number corresponding to a known clean record,
    service must return status='clean' with non-None record_meta.
    """
    collection = FakeMongoCollection()
    mrz_out = MRZOutput(
        mrz_present=True,
        mrz_fields={"doc_number": "SYN-CLN-001"},
        checksum_valid=True,
        cross_check={},
    )
    ocr_out = OCROutput(fields={}, field_confidences={}, raw_text="")

    result: DBCheckOutput = check_database(mrz_out, ocr_out, collection=collection)

    assert result.status == "clean"
    assert result.record_meta is not None
    assert result.record_meta.get("category") == "regular_traveler"


def test_blacklisted_record_returns_blacklisted() -> None:
    """
    Case 2: Blacklisted Record.
    Given a valid MRZ document number corresponding to a known blacklisted record,
    service must return status='blacklisted' with non-None record_meta.
    """
    collection = FakeMongoCollection()
    mrz_out = MRZOutput(
        mrz_present=True,
        mrz_fields={"doc_number": "SYN-BLK-001"},
        checksum_valid=True,
        cross_check={},
    )
    ocr_out = OCROutput(fields={}, field_confidences={}, raw_text="")

    result: DBCheckOutput = check_database(mrz_out, ocr_out, collection=collection)

    assert result.status == "blacklisted"
    assert result.record_meta is not None
    assert result.record_meta.get("category") == "document_fraud"


def test_watchlist_record_returns_watchlist() -> None:
    """
    Case 3: Watchlist Record.
    Given a valid MRZ document number corresponding to a known watchlist record,
    service must return status='watchlist' with non-None record_meta.
    """
    collection = FakeMongoCollection()
    mrz_out = MRZOutput(
        mrz_present=True,
        mrz_fields={"doc_number": "SYN-WCH-001"},
        checksum_valid=True,
        cross_check={},
    )
    ocr_out = OCROutput(fields={}, field_confidences={}, raw_text="")

    result: DBCheckOutput = check_database(mrz_out, ocr_out, collection=collection)

    assert result.status == "watchlist"
    assert result.record_meta is not None
    assert result.record_meta.get("category") == "enhanced_monitoring"


def test_missing_record_returns_not_found() -> None:
    """
    Case 4: Document Not Found.
    Given a valid-format document number absent from the database,
    service must return status='not_found' and record_meta=None.
    Explicitly verifies that an absent record is NEVER classified as 'clean'.
    """
    collection = FakeMongoCollection()
    mrz_out = MRZOutput(
        mrz_present=True,
        mrz_fields={"doc_number": "SYN-CLN-999-NOTFOUND"},
        checksum_valid=True,
        cross_check={},
    )
    ocr_out = OCROutput(fields={}, field_confidences={}, raw_text="")

    result: DBCheckOutput = check_database(mrz_out, ocr_out, collection=collection)

    assert result.status == "not_found"
    assert result.status != "clean"  # Explicit safety verification
    assert result.record_meta is None


def test_database_failure_returns_db_unavailable() -> None:
    """
    Case 5: Database Failure.
    Simulates a database failure (PyMongoError on find_one).
    Service must return status='db_unavailable' and record_meta=None.
    Explicitly verifies that a DB failure is NEVER classified as 'clean'.
    """
    collection = FailingMongoCollection("Simulated network timeout connecting to MongoDB")
    mrz_out = MRZOutput(
        mrz_present=True,
        mrz_fields={"doc_number": "SYN-CLN-001"},
        checksum_valid=True,
        cross_check={},
    )
    ocr_out = OCROutput(fields={}, field_confidences={}, raw_text="")

    result: DBCheckOutput = check_database(mrz_out, ocr_out, collection=collection)

    assert result.status == "db_unavailable"
    assert result.status != "clean"  # Explicit safety verification
    assert result.record_meta is None
    assert collection.call_count == 1


def test_valid_mrz_takes_priority_over_ocr() -> None:
    """
    Case 6: MRZ Priority over OCR.
    When MRZ has checksum_valid=True pointing to a blacklisted record,
    and OCR points to a clean record, MRZ takes priority.
    """
    collection = FakeMongoCollection()
    mrz_out = MRZOutput(
        mrz_present=True,
        mrz_fields={"doc_number": "SYN-BLK-001"},
        checksum_valid=True,
        cross_check={},
    )
    ocr_out = OCROutput(
        fields={"doc_number": "SYN-CLN-001"},
        field_confidences={},
        raw_text="",
    )

    result: DBCheckOutput = check_database(mrz_out, ocr_out, collection=collection)

    # MRZ record must win
    assert result.status == "blacklisted"
    assert result.record_meta is not None
    assert result.record_meta.get("category") == "document_fraud"


def test_invalid_mrz_falls_back_to_ocr() -> None:
    """
    Case 7: Invalid MRZ Falls Back to OCR.
    When MRZ checksum_valid=False, the service must ignore MRZ
    and fall back to the OCR document number.
    """
    collection = FakeMongoCollection()
    mrz_out = MRZOutput(
        mrz_present=True,
        mrz_fields={"doc_number": "SYN-BLK-001"},
        checksum_valid=False,
        cross_check={},
    )
    ocr_out = OCROutput(
        fields={"doc_number": "SYN-CLN-001"},
        field_confidences={},
        raw_text="",
    )

    result: DBCheckOutput = check_database(mrz_out, ocr_out, collection=collection)

    # OCR clean record must win
    assert result.status == "clean"
    assert result.record_meta is not None
    assert result.record_meta.get("category") == "regular_traveler"


def test_valid_checksum_but_missing_mrz_field_falls_back_to_ocr() -> None:
    """
    Case 7B: Valid Checksum but Missing MRZ Field Falls Back to OCR.
    Proves that when MRZ has checksum_valid=True but lacks a usable document number,
    the service correctly falls back to the OCR document number for database lookup.
    """
    collection = FakeMongoCollection()
    mrz_out = MRZOutput(
        mrz_present=True,
        mrz_fields={},
        checksum_valid=True,
        cross_check={},
    )
    ocr_out = OCROutput(
        fields={"doc_number": "SYN-CLN-001"},
        field_confidences={},
        raw_text="",
    )

    result: DBCheckOutput = check_database(mrz_out, ocr_out, collection=collection)

    assert result.status == "clean"
    assert result.record_meta is not None
    assert result.record_meta.get("category") == "regular_traveler"


def test_no_document_number_returns_not_found_without_db_lookup() -> None:
    """
    Case 8: No Usable Document Number.
    When neither MRZ nor OCR supplies a document number,
    service returns status='not_found' without issuing a database lookup.
    """
    collection = FakeMongoCollection()
    mrz_out = MRZOutput(
        mrz_present=False,
        mrz_fields={},
        checksum_valid=False,
        cross_check={},
    )
    ocr_out = OCROutput(
        fields={},
        field_confidences={},
        raw_text="",
    )

    result: DBCheckOutput = check_database(mrz_out, ocr_out, collection=collection)

    assert result.status == "not_found"
    assert result.record_meta is None
    # Crucial: prove no database query occurred
    assert collection.call_count == 0


def test_document_number_normalization() -> None:
    """
    Case 9: Document Number Normalization.
    Verifies that whitespace and lowercase characters are normalized
    (e.g., '  syn-cln-001  ' -> 'SYN-CLN-001') before querying the collection.
    """
    collection = FakeMongoCollection()
    mrz_out = MRZOutput(
        mrz_present=True,
        mrz_fields={"doc_number": "  syn-cln-001  "},
        checksum_valid=True,
        cross_check={},
    )
    ocr_out = OCROutput(fields={}, field_confidences={}, raw_text="")

    result: DBCheckOutput = check_database(mrz_out, ocr_out, collection=collection)

    assert result.status == "clean"
    assert result.record_meta is not None
    # Check normalized query payload
    assert collection.last_query == {"doc_number": "SYN-CLN-001"}


def test_unexpected_database_status_fails_safely() -> None:
    """
    Case 10: Unexpected Database Status.
    If the database contains an unexpected status (e.g. corrupted/tampered data),
    service must fail safely to 'db_unavailable' rather than passing as clean.
    """
    corrupt_records = [
        {
            "doc_number": "SYN-CORRUPT-001",
            "status": "something_unexpected",
            "record_meta": {"note": "corrupted status value in db"},
        }
    ]
    collection = FakeMongoCollection(records=corrupt_records)
    mrz_out = MRZOutput(
        mrz_present=True,
        mrz_fields={"doc_number": "SYN-CORRUPT-001"},
        checksum_valid=True,
        cross_check={},
    )
    ocr_out = OCROutput(fields={}, field_confidences={}, raw_text="")

    result: DBCheckOutput = check_database(mrz_out, ocr_out, collection=collection)

    assert result.status == "db_unavailable"
    assert result.status != "clean"  # Explicit safety check
    assert result.record_meta is None


# =============================================================================
# CLI Runner
# =============================================================================

if __name__ == "__main__":
    import inspect

    current_module = sys.modules[__name__]
    test_functions = [
        obj
        for name, obj in inspect.getmembers(current_module, inspect.isfunction)
        if name.startswith("test_")
    ]

    print(f"Executing {len(test_functions)} M8 Service Unit Tests:")
    print("=" * 60)

    passed_count = 0
    failed_count = 0

    for test_fn in test_functions:
        try:
            test_fn()
            print(f"  PASS: {test_fn.__name__}")
            passed_count += 1
        except Exception as exc:
            print(f"  FAIL: {test_fn.__name__}: {exc}")
            failed_count += 1

    print("=" * 60)
    print(f"Summary: {passed_count} passed, {failed_count} failed")

    if failed_count > 0:
        sys.exit(1)
