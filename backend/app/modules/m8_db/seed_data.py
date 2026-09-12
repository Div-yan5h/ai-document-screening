"""
M8 — Synthetic Database Seed Data
==================================
This module defines synthetic, mock database records for the M8 database / blacklist
check module in the AI Document Screening pipeline.

NOTICE:
All records in this module are entirely synthetic and generated strictly for
demonstration, testing, and evaluation purposes.
- NO real personal data, passport numbers, Aadhaar numbers, PAN numbers,
  or real identity credentials are used.
- All document identifiers follow an explicit synthetic naming pattern
  (e.g., 'SYN-CLN-xxx', 'SYN-BLK-xxx', 'SYN-WCH-xxx').

This file contains purely static data structures. It does not connect to MongoDB,
instantiate any database clients, or implement query/lookup logic.
"""

from typing import Any, Dict, List

# List of exactly 15 synthetic database records (5 clean, 5 blacklisted, 5 watchlist)
SEED_RECORDS: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # 1. Clean Records (5 records)
    # -------------------------------------------------------------------------
    {
        "doc_number": "SYN-CLN-001",
        "status": "clean",
        "record_meta": {
            "category": "regular_traveler",
            "reason": "No adverse records found; identity verified in synthetic registry",
            "source": "Synthetic National Registry Demo DB",
            "last_updated": "2026-08-15T10:30:00Z",
            "verification_status": "verified",
        },
    },
    {
        "doc_number": "SYN-CLN-002",
        "status": "clean",
        "record_meta": {
            "category": "frequent_flyer",
            "reason": "Pre-screened trusted traveler profile with clear security history",
            "source": "Synthetic Trusted Border Authority",
            "last_updated": "2026-07-20T14:15:00Z",
            "verification_status": "verified",
        },
    },
    {
        "doc_number": "SYN-CLN-003",
        "status": "clean",
        "record_meta": {
            "category": "diplomatic_corps",
            "reason": "Official mission accreditation; verified bilateral clearance",
            "source": "Synthetic Consular Services Registry",
            "last_updated": "2026-09-01T09:00:00Z",
            "verification_status": "verified",
        },
    },
    {
        "doc_number": "SYN-CLN-004",
        "status": "clean",
        "record_meta": {
            "category": "student_visa_holder",
            "reason": "Academic visa validated; clean screening record",
            "source": "Synthetic Immigration Portal",
            "last_updated": "2026-06-11T16:45:00Z",
            "verification_status": "verified",
        },
    },
    {
        "doc_number": "SYN-CLN-005",
        "status": "clean",
        "record_meta": {
            "category": "business_visitor",
            "reason": "Valid multi-entry commercial authorization; no border infractions",
            "source": "Synthetic Commercial Registry",
            "last_updated": "2026-08-28T11:20:00Z",
            "verification_status": "verified",
        },
    },

    # -------------------------------------------------------------------------
    # 2. Blacklisted Records (5 records)
    # -------------------------------------------------------------------------
    {
        "doc_number": "SYN-BLK-001",
        "status": "blacklisted",
        "record_meta": {
            "category": "document_fraud",
            "reason": "Reported stolen/counterfeited document series",
            "source": "Synthetic Global Stolen Document Register",
            "last_updated": "2026-08-01T08:12:00Z",
            "severity": "critical",
        },
    },
    {
        "doc_number": "SYN-BLK-002",
        "status": "blacklisted",
        "record_meta": {
            "category": "financial_sanctions",
            "reason": "Subject to international financial freeze and travel sanctions",
            "source": "Synthetic International Sanctions Bureau",
            "last_updated": "2026-07-14T12:00:00Z",
            "severity": "critical",
        },
    },
    {
        "doc_number": "SYN-BLK-003",
        "status": "blacklisted",
        "record_meta": {
            "category": "identity_theft",
            "reason": "Document invalidated following fraudulent duplicate issuance report",
            "source": "Synthetic Border Integrity Unit",
            "last_updated": "2026-09-02T15:22:00Z",
            "severity": "high",
        },
    },
    {
        "doc_number": "SYN-BLK-004",
        "status": "blacklisted",
        "record_meta": {
            "category": "customs_violations",
            "reason": "Active contraband trafficking warrant and mandatory entry exclusion",
            "source": "Synthetic Inter-Agency Enforcement Bulletin",
            "last_updated": "2026-06-30T17:40:00Z",
            "severity": "critical",
        },
    },
    {
        "doc_number": "SYN-BLK-005",
        "status": "blacklisted",
        "record_meta": {
            "category": "revoked_credential",
            "reason": "Document formally revoked by judicial court cancellation order",
            "source": "Synthetic Judicial Registry",
            "last_updated": "2026-05-19T10:05:00Z",
            "severity": "high",
        },
    },

    # -------------------------------------------------------------------------
    # 3. Watchlist Records (5 records)
    # -------------------------------------------------------------------------
    {
        "doc_number": "SYN-WCH-001",
        "status": "watchlist",
        "record_meta": {
            "category": "enhanced_monitoring",
            "reason": "Flagged for secondary screening due to transit pattern anomalies",
            "source": "Synthetic Border Control Intelligence",
            "last_updated": "2026-08-25T13:45:00Z",
            "severity": "medium",
        },
    },
    {
        "doc_number": "SYN-WCH-002",
        "status": "watchlist",
        "record_meta": {
            "category": "visa_overstay_risk",
            "reason": "Previous 30-day visa overstay notice; conditional entry review",
            "source": "Synthetic Immigration Compliance Office",
            "last_updated": "2026-07-08T09:30:00Z",
            "severity": "medium",
        },
    },
    {
        "doc_number": "SYN-WCH-003",
        "status": "watchlist",
        "record_meta": {
            "category": "pending_adjudication",
            "reason": "Pending administrative background review; requires manual verification",
            "source": "Synthetic Consular Affairs Watch",
            "last_updated": "2026-09-05T11:15:00Z",
            "severity": "low",
        },
    },
    {
        "doc_number": "SYN-WCH-004",
        "status": "watchlist",
        "record_meta": {
            "category": "potential_name_collision",
            "reason": "Potential partial match with watch bulletin; verify biometrics",
            "source": "Synthetic Watchlist Advisory Feed",
            "last_updated": "2026-08-18T18:00:00Z",
            "severity": "medium",
        },
    },
    {
        "doc_number": "SYN-WCH-005",
        "status": "watchlist",
        "record_meta": {
            "category": "currency_declaration_audit",
            "reason": "Mandatory customs audit flag for undeclared commercial assets",
            "source": "Synthetic Revenue & Customs Inspection",
            "last_updated": "2026-06-22T08:50:00Z",
            "severity": "medium",
        },
    },
]

# Convenient alias for seed script imports
SYNTHETIC_DATABASE_RECORDS = SEED_RECORDS
