# Shared Test Data & MongoDB Seed

This directory contains shared test data for validating the SIH 2026 AI Document Screening System pipeline. All test data is synthetic and contains no real personally identifiable information (PII).

## Structure
- `documents/`: Genuine (synthetic) public specimen images.
- `tampered/`: Tampered versions of the genuine specimens.
- `live-photos/`: Mock live photos for face-matching validation.
- `db-seed/`: MongoDB seed script for M8 Database validation.

## Test Data Inventory

### 1. Documents
- **`passport_clean.jpg` (DOC_001)**: Clean, synthetic passport with a valid MRZ and future expiry (2030-01-01).
- **`id_card_no_mrz.jpg` (DOC_002)**: Clean ID card with no MRZ. 
  - **IMPORTANT**: This document number (`DOC_002`) is deliberately ABSENT from the MongoDB seed to trigger the `not_found` M8 response.
- **`visa.jpg` (DOC_003)**: Clean, synthetic Visa with MRZ.
- **`passport_expired.jpg` (DOC_004)**: Genuine specimen where the expiry date is in the past (`1999-12-31`). This is meant to test the M5 rules validation logic.

### 2. Tampered Documents
- **`passport_tampered_dob.jpg` (DOC_001)**: A copy of the clean passport but the Date of Birth has been tampered with.
- **`passport_tampered_photo.jpg` (DOC_001)**: A copy of the clean passport but the photo area has been manipulated.

### 3. Live Photos
- **`live_photo_match.jpg`**: Visually matches the clean passport (DOC_001).
- **`live_photo_mismatch.jpg`**: Deliberately mismatched face to trigger negative threshold cases in M7.

## MongoDB Seed

The `db-seed/seed.py` script populates the local MongoDB instance with synthetic data matching the test documents.

### How to Run
```bash
python3 test-data/db-seed/seed.py
```
*(Requires `pymongo` and a running MongoDB instance at `localhost:27017` or configured via `MONGO_URI`)*

### Supported M8 Statuses
The script strictly uses ONLY the following locked M8 statuses:
- `clean` (7 records)
- `blacklisted` (3 records)
- `watchlist` (2 records)

### Notes on Excluded DB Statuses
- **`not_found`**: This is NOT seeded. It is naturally produced by querying a document number that has no record (e.g., query for `DOC_002`).
- **`db_unavailable`**: This is NOT seeded. It is a runtime MongoDB connection failure, completely independent of seed data.
- **`expired`**: This is NOT an M8 database status. Expiry logic is determined by M5 reading the document's expiry date field.
