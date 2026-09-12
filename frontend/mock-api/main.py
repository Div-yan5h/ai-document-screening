import os
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="P5 Frontend Temporary Mock API",
    description="Mock backend server for P5 Next.js frontend testing prior to P1 integration.",
    version="1.0.0"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mock_database = {
    "P1234567": {
        "status": "clean",
        "name": "TEST USER"
    },
    "P9999999": {
        "status": "blacklisted",
        "name": "BLACKLISTED USER"
    }
}


@app.post("/screen")
async def screen_document(
    doc_file: UploadFile = File(...),
    live_photo: UploadFile = File(...),
    scenario: Optional[str] = Query(None)
):
    selected_scenario = (scenario or os.getenv("MOCK_SCENARIO", "clean")).strip().lower()

    # Default clean response values
    session_id = f"MOCK-{selected_scenario.upper()}-001"
    
    doc_type = "passport"
    doc_type_confidence = 0.97
    doc_bbox = [0, 0, 1000, 700]

    ocr_fields = {
        "doc_number": "P1234567",
        "name": "TEST USER",
        "dob": "1995-01-15",
        "nationality": "IND",
        "expiry_date": "2030-01-15"
    }
    field_confidences = {
        "doc_number": 0.98,
        "name": 0.96,
        "dob": 0.95,
        "nationality": 0.99,
        "expiry_date": 0.97
    }
    raw_text = "MOCK PASSPORT OCR TEXT"

    mrz_present = True
    mrz_fields = {
        "document_number": "P1234567",
        "nationality": "IND"
    }
    checksum_valid = True
    cross_check = {
        "document_number": True,
        "name": True,
        "dob": True
    }

    is_expired = False
    format_valid = True
    logic_valid = True
    flags = []

    suspicion_score = 0.02
    flagged_regions = []
    signals = {}

    similarity = 0.92
    match_band = "confident_match"
    liveness_passed = True

    db_status = "clean"
    record_meta = {
        "source": "MOCK_DATABASE",
        "test_record": True
    }

    risk_score = 2
    risk_band = "low"
    reasons = ["No significant risk factors detected"]
    contributions = {
        "blacklist_hit": 0.0,
        "expired": 0.0,
        "ocr_mrz_mismatch": 0.0,
        "face_mismatch": 0.01,
        "tamper_suspicion": 0.002,
        "low_ocr_confidence": 0.0
    }

    # Scenario Adjustments
    if selected_scenario == "blacklisted":
        db_status = "blacklisted"
        ocr_fields["doc_number"] = "P9999999"
        ocr_fields["name"] = "BLACKLISTED USER"
        mrz_fields["document_number"] = "P9999999"
        risk_score = 30
        risk_band = "medium"
        reasons = ["Document is blacklisted in immigration database"]
        contributions["blacklist_hit"] = 0.30

    elif selected_scenario == "expired":
        is_expired = True
        ocr_fields["expiry_date"] = "2020-01-15"
        flags = ["Document has expired"]
        risk_score = 20
        risk_band = "low"
        reasons = ["Document has expired"]
        contributions["expired"] = 0.20

    elif selected_scenario == "face_mismatch":
        similarity = 0.20
        match_band = "no_match"
        liveness_passed = False
        risk_score = 20
        risk_band = "low"
        reasons = ["Face photo does not match live photo (similarity: 20%)"]
        contributions["face_mismatch"] = 0.20

    elif selected_scenario == "high_risk":
        db_status = "blacklisted"
        is_expired = True
        cross_check = {
            "document_number": False,
            "name": True,
            "dob": True
        }
        similarity = 0.20
        match_band = "no_match"
        suspicion_score = 0.90
        field_confidences["name"] = 0.65
        risk_score = 95
        risk_band = "high"
        reasons = [
            "Document is blacklisted in immigration database",
            "Document has expired",
            "Face photo does not match live photo (similarity: 20%)"
        ]
        contributions = {
            "blacklist_hit": 0.30,
            "expired": 0.20,
            "ocr_mrz_mismatch": 0.15,
            "face_mismatch": 0.16,
            "tamper_suspicion": 0.09,
            "low_ocr_confidence": 0.05
        }

    return {
        "session_id": session_id,
        "classifier": {
            "doc_type": doc_type,
            "doc_type_confidence": doc_type_confidence,
            "doc_bbox": doc_bbox
        },
        "ocr": {
            "fields": ocr_fields,
            "field_confidences": field_confidences,
            "raw_text": raw_text
        },
        "mrz": {
            "mrz_present": mrz_present,
            "mrz_fields": mrz_fields,
            "checksum_valid": checksum_valid,
            "cross_check": cross_check
        },
        "rules": {
            "is_expired": is_expired,
            "format_valid": format_valid,
            "logic_valid": logic_valid,
            "flags": flags
        },
        "tamper": {
            "suspicion_score": suspicion_score,
            "flagged_regions": flagged_regions,
            "signals": signals
        },
        "face": {
            "similarity": similarity,
            "match_band": match_band,
            "liveness_passed": liveness_passed
        },
        "db": {
            "status": db_status,
            "record_meta": record_meta
        },
        "risk": {
            "risk_score": risk_score,
            "risk_band": risk_band,
            "reasons": reasons,
            "contributions": contributions
        }
    }
