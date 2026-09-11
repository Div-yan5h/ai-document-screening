# Build Spec — AI Document Screening System
**5-person module split, exact I/O contracts, and build logic per module.**

Core rule for working in parallel (especially with agentic tools like Antigravity building per-folder): **nobody touches another module's internals — everyone codes to the JSON contract below.** Freeze these contracts first, in a shared file, before anyone writes pipeline logic. That single step prevents 90% of "it doesn't merge" pain on integration day.

---

## 0. Repo Structure

```
/backend
  /app
    /schemas/            ← contracts.py (Pydantic models — SOURCE OF TRUTH, freeze this first)
    /modules/
      /m1_ingestion/      → P1
      /m2_classifier/     → P2
      /m3_ocr/            → P2
      /m4_mrz/            → P3
      /m5_rules/          → P3
      /m6_tamper/         → P3
      /m7_face/           → P4
      /m8_db/             → P4
      /m9_risk_engine/    → P5
    /orchestrator/
      pipeline.py         ← P1 owns: calls modules in order, wires outputs→inputs
    main.py               ← FastAPI app, P1 owns
/frontend                 ← Next.js, P5 owns (upload UI + officer dashboard)
```

Each module folder = one or more `.py` files owned by one person, exposing **one function** with a fixed signature: `def run(input: ModuleXInput) -> ModuleXOutput`. The orchestrator only ever calls `run()` — it never reaches into a module's internals. This is what lets 5 people build in parallel and merge without conflicts.

---

## 1. Team Split

| Person | Owns | Why grouped this way |
|---|---|---|
| **P1 — Platform Lead** | Ingestion/preprocessing (M1) + Orchestrator/FastAPI main controller + integration glue + demo data | Needs to exist first (everyone else depends on M1's output) and last (merges everyone) — most senior/available person |
| **P2 — Document Understanding** | Document classifier (M2) + OCR (M3) | Both are "read the document" — natural pairing, shares image-preprocessing context |
| **P3 — Document Integrity** | MRZ parser + cross-check (M4) + Rule validation (M5) + Tamper heuristic (M6) | All three are "is this document internally consistent" logic — no CV/ML model training needed, mostly deterministic + OpenCV |
| **P4 — Identity & Records** | Face verification (M7) + DB/blacklist check (M8) | Both are "match against something external" — person and record |
| **P5 — Risk & Experience** | Risk engine (M9) + Next.js frontend (upload UI + officer dashboard) | Owns the thing judges actually see — needs to understand every module's output to design the UI, so pairs naturally with the scoring logic |

**Dependency order:** P1's M1 must exist (even as a stub) by hour 2 — everyone else builds against it. Everything from M2–M8 can be built **in parallel** once contracts are frozen, since none of them depend on each other's actual code, only on the schema. M9 (P5) is the only module that depends on everyone else's real output, so P5 builds the risk engine against **mocked/fake outputs** matching the contract until real modules land, then swaps them in.

---

## 2. Frozen I/O Contracts

Put this in `/backend/app/schemas/contracts.py` as Pydantic models on hour 0. Everyone builds against this file; nobody edits it alone after hour 2 without telling the group.

```python
# M1 → everything downstream
class IngestionOutput(BaseModel):
    session_id: str
    doc_image_path: str      # preprocessed (deskewed/denoised) image
    live_photo_path: str
    doc_type_hint: str | None = None

# M2 → M3, M9
class ClassifierOutput(BaseModel):
    doc_type: str             # "passport" | "visa" | "id_card" | "unknown"
    doc_type_confidence: float
    doc_bbox: list[int] | None = None

# M3 → M4, M5, M9
class OCROutput(BaseModel):
    fields: dict[str, str]    # name, dob, doc_number, expiry_date, nationality, issue_date
    field_confidences: dict[str, float]
    raw_text: str

# M4 → M9
class MRZOutput(BaseModel):
    mrz_present: bool
    mrz_fields: dict[str, str]
    checksum_valid: bool
    cross_check: dict[str, bool]   # name_match, dob_match, doc_number_match, expiry_match

# M5 → M9
class RuleValidationOutput(BaseModel):
    is_expired: bool
    format_valid: bool
    logic_valid: bool
    flags: list[str]          # human-readable reasons

# M6 → M9
class TamperOutput(BaseModel):
    suspicion_score: float        # 0–1
    flagged_regions: list[list[int]]
    signals: dict[str, float]     # ela_score, copy_move_score, font_inconsistency_score

# M7 → M9
class FaceVerificationOutput(BaseModel):
    similarity: float             # 0–1
    match_band: str               # "confident_match" | "review" | "likely_mismatch"
    liveness_passed: bool | None  # null if not implemented

# M8 → M9
class DBCheckOutput(BaseModel):
    status: str                   # "clean" | "blacklisted" | "watchlist" | "not_found" | "db_unavailable"
    record_meta: dict | None = None

# M9 → frontend
class RiskEngineOutput(BaseModel):
    risk_score: int               # 0–100
    risk_band: str                # "low" | "medium" | "high"
    reasons: list[str]
    contributions: dict[str, float]  # per-module weighted contribution, for the "why" UI
```

---

## 3. Exact Build Logic, Per Module

### M1 — Ingestion & Preprocessing (P1)
1. FastAPI endpoint accepts `POST /screen` with two files: document image, live photo.
2. Save both to disk/temp storage under a generated `session_id`.
3. Run OpenCV: grayscale → deskew (Hough transform or minAreaRect on largest contour) → denoise (fastNlMeansDenoising) → contrast enhance (CLAHE).
4. Save preprocessed image, return `IngestionOutput`.
5. **Build this first as a stub that just copies the raw image through** — unblocks everyone else within the first hour, add real OpenCV logic after.

### M2 — Document Classifier (P2)
1. Collect/label a small dataset: 20–40 sample images per class (passport, visa, ID card) — use public sample/specimen document images.
2. Fine-tune a small YOLO classification head or a lightweight CNN (transfer learning off MobileNet/ResNet18 is faster to train than YOLO detection if you only need whole-image classification, not bounding boxes).
3. Input: `doc_image_path` from M1. Output: `doc_type`, confidence.
4. If confidence < threshold (e.g. 0.6), return `"unknown"` — don't force a wrong label downstream.
5. **Fallback for demo safety:** if training doesn't converge well in time, hardcode a rule-based fallback (e.g., aspect ratio + presence of MRZ-like text block near bottom = passport) so the pipeline never hard-fails.

### M3 — OCR (P2)
1. Run PaddleOCR on the preprocessed image → raw text + bounding boxes.
2. Map raw OCR output to named fields (`name`, `dob`, `doc_number`, `expiry_date`, `nationality`, `issue_date`) using regex/positional heuristics specific to `doc_type` from M2 (e.g., passport layouts have a known field-position convention).
3. Attach a confidence per field (PaddleOCR gives per-box confidence — use the box confidence for the field it maps to).
4. Output `OCROutput`.

### M4 — MRZ Parser + Cross-Check (P3)
1. Crop the MRZ zone (bottom of passport/ID — fixed relative position, or detect the two/three monospace lines via OpenCV text-line detection).
2. OCR the MRZ zone separately (MRZ font is more OCR-friendly — treat this as its own smaller OCR pass, don't reuse M3's general output).
3. Parse per ICAO Doc 9303 format: fixed-width fields, compute and verify the built-in checksum digits.
4. Cross-check each MRZ field against the corresponding M3 OCR field → set `cross_check` booleans.
5. If no MRZ zone detected at all (e.g., ID card without MRZ), set `mrz_present = false` and skip cross-check cleanly — don't crash the pipeline.

### M5 — Rule Validation (P3)
1. Input: OCR fields + MRZ fields (prefer MRZ value when both exist and checksum is valid — it's more reliable).
2. Check expiry: `expiry_date < today` → `is_expired = true`.
3. Check logical consistency: `issue_date < expiry_date`, `dob` is a plausible age range.
4. Check format: doc number matches expected pattern for `doc_type`.
5. Populate `flags` with a plain-English reason for every failed check — this feeds directly into the officer's "why" display later, so write these as full sentences now, not codes.

### M6 — Tamper Heuristic (P3)
1. **ELA:** re-save the image at fixed JPEG quality (e.g. 90), diff against original, threshold the diff map, take the max/mean error in high-error regions as `ela_score`.
2. **Copy-move:** ORB or SIFT keypoint detection within the image, match keypoints against each other (not against a second image), flag clusters of near-identical matched regions as `copy_move_score`.
3. **Font/spacing consistency:** for OCR'd text fields (from M3), compute character-height and spacing statistics per field; flag fields whose stats deviate significantly from the document's overall average as `font_inconsistency_score`.
4. Combine the three into a single `suspicion_score` (simple average or max — document your choice, don't overthink it, this is a heuristic not a model).
5. **Label everything downstream as "suspicion," never "confirmed tampering."**

### M7 — Face Verification (P4)
1. Detect and crop the face region from the document photo (most document images have the photo in a fixed corner, or run a face detector like RetinaFace/MTCNN to locate it).
2. Detect and crop the face from the live photo.
3. Generate embeddings for both using ArcFace/InsightFace.
4. Compute cosine similarity between embeddings.
5. Map similarity to bands: e.g. `>0.75` → `confident_match`, `0.5–0.75` → `review`, `<0.5` → `likely_mismatch` — tune these thresholds against your own test images before the demo, don't ship the first numbers you guess.
6. `liveness_passed`: set to `null` unless you build the stretch-goal active-liveness check (§ below).

### M8 — DB / Blacklist Check (P4)
1. Seed a MongoDB collection with synthetic records: mix of valid, expired, and blacklisted `doc_number`s — generate these yourself, don't use real data.
2. Input: `doc_number` (prefer MRZ value if valid, else OCR value).
3. Query by `doc_number`. If found: return its stored status. If not found: return `"not_found"` (don't default this to `"clean"` — absence of a record isn't proof of innocence).
4. Wrap the query in a try/except — on any DB connection failure, return `"db_unavailable"` explicitly, never let it silently pass as clean.

### M9 — Risk Engine (P5)
1. Collect all module outputs for a session (orchestrator passes the full merged object in).
2. Normalize each signal to 0–1:
   - `blacklist_hit` = 1 if M8 status is `blacklisted`/`watchlist`, else 0
   - `expired` = 1 if M5 `is_expired`, else 0
   - `ocr_mrz_mismatch` = 1 if any M4 `cross_check` value is false (and MRZ present + checksum valid)
   - `face_mismatch` = `1 - M7.similarity`
   - `tamper_suspicion` = M6 `suspicion_score`
3. Apply weights (suggested starting point — justify and tune, don't leave unexplained):
   - blacklist_hit: 0.30
   - expired: 0.20
   - ocr_mrz_mismatch: 0.20
   - face_mismatch: 0.20
   - tamper_suspicion: 0.10 *(weighted lowest — it's the least deterministic signal)*
4. `risk_score = round(100 * Σ(weight_i × signal_i))`.
5. Band it: `<30` low, `30–70` medium, `>70` high.
6. Build `reasons` by taking every signal whose normalized value is above a small threshold (e.g. >0.3) and converting it to a plain-English sentence, sorted by contribution size, top 3 shown.
7. Return `RiskEngineOutput`.

### M10 — Officer Dashboard (P5, frontend)
1. Upload screen: two file inputs (document, live photo capture via webcam or upload) → `POST /screen`.
2. Results screen: show `risk_score` + colored band, the top reasons list, and a breakdown panel showing each module's raw output (OCR fields, face similarity number, DB status) — officers should be able to drill into *why*, not just see the number.
3. Officer action buttons: Approve / Deny / Escalate → `POST /decision` storing the officer's call + session ID + timestamp (this is your audit log, cheap to add, mentioned in the review doc's privacy section).

---

## 4. Orchestrator Logic (P1 owns, wires everyone else's `run()` together)

```
def pipeline(doc_file, live_photo_file):
    ingestion_out = m1_ingestion.run(doc_file, live_photo_file)

    classifier_out = m2_classifier.run(ingestion_out)
    ocr_out        = m3_ocr.run(ingestion_out, classifier_out)

    mrz_out   = m4_mrz.run(ingestion_out, ocr_out)
    rules_out = m5_rules.run(ocr_out, mrz_out)
    tamper_out = m6_tamper.run(ingestion_out, ocr_out)        # can run in parallel with M4/M5

    face_out = m7_face.run(ingestion_out)                     # can run in parallel with M4/M5/M6
    db_out   = m8_db.run(mrz_out, ocr_out)                    # can run in parallel with M7

    risk_out = m9_risk_engine.run(
        classifier_out, ocr_out, mrz_out, rules_out, tamper_out, face_out, db_out
    )

    return risk_out, {all raw module outputs for dashboard drill-down}
```

Use `asyncio.gather()` for the two parallel groups (M4/M5/M6 vs M7/M8) if you want real speed — not required for the demo to work, just makes the "15–30 sec" claim from your deck actually true if you decide to keep a number like that.

---

## 5. Build Order (rough hour-by-hour for a ~30-hour build window)

| Hours | What happens |
|---|---|
| 0–2 | Everyone in one room: freeze `contracts.py` together. P1 stubs M1. Repo skeleton up. |
| 2–14 | Parallel build: P2 (M2+M3), P3 (M4+M5+M6), P4 (M7+M8), P5 builds M9 + frontend against **fake/mocked module outputs matching the contract** (don't wait on real ones) |
| 14–18 | First integration pass: P1 wires everyone's real `run()` functions into the orchestrator, one module at a time, testing after each swap-in |
| 18–24 | Bug fixing + threshold tuning (face similarity bands, risk weights) against your actual prepared demo documents |
| 24–28 | Dashboard polish, prepare your 3 demo cases (clean / tampered / blacklisted — see the review doc §12), rehearse |
| 28–30 | Buffer — something will break here, budget for it |

---

## 6. Test Data You Need to Prepare Yourselves

- 3–5 genuine sample document images (public specimen passports/IDs — not real people's documents)
- 1–2 of the above, manually edited by you (Photoshop/GIMP: change a DOB field, or paste a different photo) — this is your **known-tampered ground truth**, needed for M6 testing and your demo
- A synthetic MongoDB seed script: 10–15 fake records, mix of clean/expired/blacklisted
- Matching live-photo pairs for face verification testing (can be your own team's photos against document-style crops of yourselves)

Build this test data on hour 0–2 alongside the contract freeze — every module needs it to test against, so it can't be an afterthought.
