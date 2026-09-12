"""
M8 — MongoDB Connection Layer
==============================
Provides reusable MongoDB client, database, and collection handles with
configurable connection URIs and fail-fast timeouts.

Owner: P4 (Identity & Records)
"""

import os
from typing import Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, PyMongoError, ServerSelectionTimeoutError

# Configuration defaults
DEFAULT_MONGO_URI = "mongodb://localhost:27017/"
DEFAULT_DB_NAME = "document_screening"
DEFAULT_COLLECTION_NAME = "blacklist"
DEFAULT_TIMEOUT_MS = 2000  # 2000 ms fast-fail to prevent pipeline blocking


def get_mongo_uri() -> str:
    """Return configured MongoDB URI from environment variable MONGODB_URI or default."""
    return os.getenv("MONGODB_URI", DEFAULT_MONGO_URI)


def get_mongo_client(
    uri: Optional[str] = None,
    timeout_ms: int = DEFAULT_TIMEOUT_MS,
) -> MongoClient:
    """
    Create and return a configured MongoClient.

    Configured with a short serverSelectionTimeoutMS so an unreachable
    MongoDB instance fails fast without stalling the screening pipeline.
    """
    connection_uri = uri or get_mongo_uri()
    return MongoClient(
        connection_uri,
        serverSelectionTimeoutMS=timeout_ms,
        connectTimeoutMS=timeout_ms,
        socketTimeoutMS=timeout_ms,
    )


def get_database(
    db_name: Optional[str] = None,
    client: Optional[MongoClient] = None,
) -> Database:
    """Return the screening database handle using the configured or provided client."""
    active_client = client if client is not None else get_mongo_client()
    target_db_name = db_name or os.getenv("MONGODB_DB_NAME", DEFAULT_DB_NAME)
    return active_client[target_db_name]


def get_blacklist_collection(
    collection_name: Optional[str] = None,
    client: Optional[MongoClient] = None,
) -> Collection:
    """Return the collection handle for blacklist/watchlist document records."""
    db = get_database(client=client)
    target_coll_name = collection_name or os.getenv("MONGODB_COLLECTION_NAME", DEFAULT_COLLECTION_NAME)
    return db[target_coll_name]


def ping_connection(client: Optional[MongoClient] = None) -> bool:
    """
    Verify if MongoDB is reachable within the fast-fail timeout window.

    Returns True if healthy, False if unreachable or timed out.
    """
    active_client = client if client is not None else get_mongo_client()
    try:
        active_client.admin.command("ping")
        return True
    except (ServerSelectionTimeoutError, ConnectionFailure, PyMongoError):
        return False
