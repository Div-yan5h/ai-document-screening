import os
import sys
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Locked M8 Statuses
STATUS_CLEAN = "clean"
STATUS_BLACKLISTED = "blacklisted"
STATUS_WATCHLIST = "watchlist"

# The documents to seed. 
# We use synthetic doc numbers that match our generated images.
# IMPORTANT: DOC_002 is DELIBERATELY ABSENT to test 'not_found'.
SEED_DATA = [
    # 7 Clean records
    {"doc_number": "DOC_001", "status": STATUS_CLEAN, "meta": {"name": "JOHN DOE"}},
    {"doc_number": "DOC_003", "status": STATUS_CLEAN, "meta": {"name": "ALICE WONG"}},
    {"doc_number": "DOC_004", "status": STATUS_CLEAN, "meta": {"name": "BOB OLD", "note": "Expired but clean"}},
    {"doc_number": "DOC_CLEAN_100", "status": STATUS_CLEAN, "meta": {"name": "CLEAN RECORD 1"}},
    {"doc_number": "DOC_CLEAN_101", "status": STATUS_CLEAN, "meta": {"name": "CLEAN RECORD 2"}},
    {"doc_number": "DOC_CLEAN_102", "status": STATUS_CLEAN, "meta": {"name": "CLEAN RECORD 3"}},
    {"doc_number": "DOC_CLEAN_103", "status": STATUS_CLEAN, "meta": {"name": "CLEAN RECORD 4"}},
    
    # 3 Blacklisted records
    {"doc_number": "DOC_001_TAMPERED_DOB", "status": STATUS_BLACKLISTED, "meta": {"reason": "Known counterfeit format"}},
    {"doc_number": "DOC_001_TAMPERED_PHOTO", "status": STATUS_BLACKLISTED, "meta": {"reason": "Stolen identity"}},
    {"doc_number": "DOC_BLACKLIST_200", "status": STATUS_BLACKLISTED, "meta": {"reason": "Fraud ring"}},
    
    # 2 Watchlist records
    {"doc_number": "DOC_WATCH_300", "status": STATUS_WATCHLIST, "meta": {"reason": "Suspicious activity"}},
    {"doc_number": "DOC_WATCH_301", "status": STATUS_WATCHLIST, "meta": {"reason": "Pending investigation"}},
]

def get_mongo_client():
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=2000)
    return client

def seed():
    logger.info("Starting M8 MongoDB seed script...")
    
    client = get_mongo_client()
    try:
        # Check connection
        client.admin.command('ping')
        logger.info("Successfully connected to MongoDB.")
    except ConnectionFailure:
        logger.error("Could not connect to MongoDB. Is it running?")
        logger.info("Skipping actual DB insertion for local validation, but seed data is validated.")
        validate_seed_data()
        return

    db = client["document_screening"]
    collection = db["records"]
    
    # Clear existing test data to avoid duplicates
    collection.delete_many({})
    
    # Insert new data
    collection.insert_many(SEED_DATA)
    
    logger.info(f"Successfully seeded {len(SEED_DATA)} records.")
    
    # Validate statuses directly from DB
    validate_seed_data_from_db(collection)

def validate_seed_data():
    valid_statuses = {STATUS_CLEAN, STATUS_BLACKLISTED, STATUS_WATCHLIST}
    
    counts = {s: 0 for s in valid_statuses}
    for record in SEED_DATA:
        status = record["status"]
        if status not in valid_statuses:
            logger.error(f"INVALID STATUS FOUND: {status}")
            sys.exit(1)
        counts[status] += 1
        
    logger.info(f"Seed data validated. Counts: {counts}")
    
    absent_doc = "DOC_002"
    if any(r["doc_number"] == absent_doc for r in SEED_DATA):
        logger.error(f"DOC {absent_doc} was found in seed data! It should be absent.")
        sys.exit(1)
    else:
        logger.info(f"Confirmed {absent_doc} is deliberately absent to test 'not_found'.")

def validate_seed_data_from_db(collection):
    valid_statuses = {STATUS_CLEAN, STATUS_BLACKLISTED, STATUS_WATCHLIST}
    
    # Fetch all to verify
    records = list(collection.find({}))
    
    counts = {s: 0 for s in valid_statuses}
    for record in records:
        status = record["status"]
        if status not in valid_statuses:
            logger.error(f"INVALID STATUS FOUND IN DB: {status}")
            sys.exit(1)
        counts[status] += 1
        
    logger.info(f"DB records validated. Counts: {counts}")
    
    absent_doc = "DOC_002"
    if collection.find_one({"doc_number": absent_doc}):
        logger.error(f"DOC {absent_doc} was found in DB! It should be absent.")
        sys.exit(1)
    else:
        logger.info(f"Confirmed {absent_doc} is deliberately absent in DB to test 'not_found'.")

if __name__ == "__main__":
    seed()
