"""
Frozen I/O Contracts — Source of Truth
======================================
Pydantic models defining the exact input/output interfaces between all modules.

From Build Spec §2: "Put this in /backend/app/schemas/contracts.py as Pydantic models
on hour 0. Everyone builds against this file; nobody edits it alone after hour 2
without telling the group."

DO NOT EDIT without team consensus.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel


# M1 → everything downstream
class IngestionOutput(BaseModel):
    session_id: str
    doc_image_path: str      # preprocessed (deskewed/denoised) image
    live_photo_path: str
    doc_type_hint: Optional[str] = None


# M2 → M3, M9
class ClassifierOutput(BaseModel):
    doc_type: str             # "passport" | "visa" | "id_card" | "unknown"
    doc_type_confidence: float
    doc_bbox: Optional[List[int]] = None


# M3 → M4, M5, M9
class OCROutput(BaseModel):
    fields: Dict[str, str]    # name, dob, doc_number, expiry_date, nationality, issue_date
    field_confidences: Dict[str, float]
    raw_text: str


# M4 → M9
class MRZOutput(BaseModel):
    mrz_present: bool
    mrz_fields: Dict[str, str]
    checksum_valid: bool
    cross_check: Dict[str, bool]   # name_match, dob_match, doc_number_match, expiry_match


# M5 → M9
class RuleValidationOutput(BaseModel):
    is_expired: bool
    format_valid: bool
    logic_valid: bool
    flags: List[str]          # human-readable reasons


# M6 → M9
class TamperOutput(BaseModel):
    suspicion_score: float        # 0–1
    flagged_regions: List[List[int]]
    signals: Dict[str, float]     # ela_score, copy_move_score, font_inconsistency_score


# M7 → M9
class FaceVerificationOutput(BaseModel):
    similarity: float             # 0–1
    match_band: str               # "confident_match" | "review" | "likely_mismatch"
    liveness_passed: Optional[bool] = None  # null if not implemented


# M8 → M9
class DBCheckOutput(BaseModel):
    status: str                   # "clean" | "blacklisted" | "watchlist" | "not_found" | "db_unavailable"
    record_meta: Optional[dict] = None


# M9 → frontend
class RiskEngineOutput(BaseModel):
    risk_score: int               # 0–100
    risk_band: str                # "low" | "medium" | "high"
    reasons: List[str]
    contributions: Dict[str, float]  # per-module weighted contribution, for the "why" UI
