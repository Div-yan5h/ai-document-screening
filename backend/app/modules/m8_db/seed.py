"""
M8 — MongoDB Database Seeder
============================
Populates the M8 database collection with synthetic screening records
from seed_data.py using idempotent upsert operations.

Usage:
    python -m backend.app.modules.m8_db.seed

Owner: P4 (Identity & Records)
"""

import sys
from typing import Any, Dict, Optional

from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from backend.app.modules.m8_db.connection import (
    get_blacklist_collection,
    get_mongo_uri,
    ping_connection,
)
from backend.app.modules.m8_db.seed_data import SEED_RECORDS


def seed_database(collection: Optional[Collection] = None) -> Dict[str, Any]:
    """
    Seed the configured M8 MongoDB collection with synthetic records.

    Ensures idempotency and uniqueness by creating a unique index on 'doc_number'
    and using upsert (update_one with $set) for each record.

    Args:
        collection: Optional PyMongo collection instance. If omitted, uses the
                    default configured collection from connection.py.

    Returns:
        Dict containing execution metrics and target collection details.

    Raises:
        ConnectionError: If MongoDB is not reachable.
        PyMongoError: If an error occurs during database operations.
    """
    target_collection = collection if collection is not None else get_blacklist_collection()
    client = target_collection.database.client

    # Verify connectivity before performing write operations
    if not ping_connection(client=client):
        raise ConnectionError(
            f"Cannot connect to MongoDB at '{get_mongo_uri()}'. "
            "Ensure the MongoDB daemon is running and accessible."
        )

    # Enforce uniqueness constraint on document number
    target_collection.create_index("doc_number", unique=True)

    total_processed = 0
    upserted_count = 0
    modified_count = 0
    matched_count = 0

    for record in SEED_RECORDS:
        doc_number = record.get("doc_number")
        if not doc_number:
            continue

        result = target_collection.update_one(
            {"doc_number": doc_number},
            {"$set": record},
            upsert=True,
        )

        total_processed += 1
        if result.upserted_id is not None:
            upserted_count += 1
        elif result.modified_count > 0:
            modified_count += 1
        else:
            matched_count += 1

    return {
        "status": "success",
        "database": target_collection.database.name,
        "collection": target_collection.name,
        "total_processed": total_processed,
        "upserted_count": upserted_count,
        "modified_count": modified_count,
        "matched_count": matched_count,
    }


def main() -> None:
    """CLI entrypoint for running database seeding."""
    print("Connecting to MongoDB and initiating M8 database seeding...")
    try:
        summary = seed_database()
        print("\n=== M8 MongoDB Seeding Summary ===")
        print(f"Database:           {summary['database']}")
        print(f"Collection:         {summary['collection']}")
        print(f"Total Processed:    {summary['total_processed']}")
        print(f"Newly Inserted:     {summary['upserted_count']}")
        print(f"Updated:            {summary['modified_count']}")
        print(f"Already Up-To-Date: {summary['matched_count']}")
        print("Status:             SUCCESS")
        sys.exit(0)
    except ConnectionError as err:
        print(f"\n[ERROR] Connection failed: {err}", file=sys.stderr)
        sys.exit(1)
    except PyMongoError as err:
        print(f"\n[ERROR] MongoDB operation failed: {err}", file=sys.stderr)
        sys.exit(1)
    except Exception as err:
        print(f"\n[ERROR] Unexpected error during seeding: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
