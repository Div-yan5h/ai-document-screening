# INTEGRATION AUDIT: AI Document Screening System
**Complete Backend → Frontend & Module Connection Audit Report**

- **Repository Root:** `c:\Users\hp\ai-document-screening`
- **File Location:** `INTEGRATION_AUDIT.md`
- **Generated At:** 2026-09-13
- **Auditor:** DeepMind Antigravity Integration Audit Agent
- **Purpose:** Comprehensive, implementation-ready blueprint for connecting Frontend → API → Orchestrator → Modules M1–M9 → Frontend UI without altering existing core module algorithms.

---

## 1. Complete Repository Architecture

The repository implements a travel credential verification and identity fraud detection pipeline designed for immigration officers. It is divided into two primary subsystems:

```
c:\Users\hp\ai-document-screening
├── backend/
│   ├── app/
│   │   ├── main.py                      # [STUB] FastAPI application entry point (currently 9 lines of comments)
│   │   ├── orchestrator/
│   │   │   ├── __init__.py
│   │   │   └── pipeline.py              # Pipeline controller calling M1–M9
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── contracts.py             # Frozen Pydantic models (source of truth)
│   │   └── modules/
│   │       ├── m1_ingestion/            # Ingestion & OpenCV preprocessing
│   │       ├── m2_classifier/           # MobileNetV3 + Heuristic Document Classifier
│   │       ├── m3_ocr/                  # PaddleOCR engine + FieldExtractor
│   │       ├── m4_mrz/                  # OpenCV MRZ crop + Tesseract + ICAO Doc 9303 check
│   │       ├── m5_rules/                # Pure Python rule validation & expiry logic
│   │       ├── m6_tamper/               # ELA + Copy-Move ORB + Font inconsistency
│   │       ├── m7_face/                 # InsightFace ArcFace biometric face verification
│   │       ├── m8_db/                   # MongoDB synthetic blacklist/watchlist queries
│   │       └── m9_risk_engine/          # Weighted risk score & human-readable reason generator
│   └── requirements.txt                 # Backend dependency list
├── frontend/
│   ├── app/
│   │   ├── components/
│   │   │   ├── UploadForm.tsx           # Document & Live Photo upload form (Axios multipart/form-data)
│   │   │   └── ResultsDashboard.tsx     # Officer dashboard (Risk score, 4-card grid, OCR overview)
│   │   ├── types/
│   │   │   └── contracts.ts             # TypeScript interfaces matching backend models + ScreeningResult
│   │   ├── page.tsx                     # Main single-page application entry point
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── mock-api/                        # Temporary mock FastAPI server used by P5
│   │   └── main.py                      # Standalone mock returning mock ScreeningResult
│   ├── package.json
│   ├── tsconfig.json
│   └── tailwind.config.ts
├── test_images/                         # Test PNG portraits and documents (personA1.png, etc.)
├── sih_build_spec.md                    # Core project specifications and I/O contracts
└── SIH2026_Team_Build_Guide.md          # Multi-person team development guide
```

### Key Architectural Characteristics:
1. **Source of Truth Contracts:** Every module communicates exclusively through frozen Pydantic contracts declared in `backend/app/schemas/contracts.py`.
2. **Single Entry Point Per Module:** Every module folder `m1_ingestion` through `m9_risk_engine` exposes a single entry function named `run()` in `handler.py`.
3. **Decoupled Architecture:** No module reaches into another module's internal classes or database connections. The orchestrator (`pipeline.py`) is responsible for chaining them.

---

## 2. Every Backend Module (M1–M9) & Exact Entry Function

### Module M1: Ingestion & Preprocessing
* **Module Folder:** `backend/app/modules/m1_ingestion`
* **Handler File:** `backend/app/modules/m1_ingestion/handler.py`
* **Exact Entry Function:** 
  ```python
  def run(doc_image_bytes: bytes, live_photo_bytes: bytes, doc_type_hint: Optional[str] = None) -> IngestionOutput
  ```
* **Internal Execution:** Saves raw images to `storage/sessions/{session_id}/doc_raw.jpg` and `live_photo.jpg`. Applies OpenCV deskew (`minAreaRect`), denoise (`fastNlMeansDenoising`), and contrast enhancement (`CLAHE`). Saves to `doc_preprocessed.jpg`.

### Module M2: Document Classifier
* **Module Folder:** `backend/app/modules/m2_classifier`
* **Handler File:** `backend/app/modules/m2_classifier/handler.py`
* **Exact Entry Function:** 
  ```python
  def run(ingestion_out: IngestionOutput) -> ClassifierOutput
  ```
* **Internal Execution:** Instantiates `DocumentClassifier` in `classifier.py`. Uses MobileNetV3-Small (`models/m2_classifier/m2_classifier.pth`). If model unavailable or confidence < 0.6, triggers aspect-ratio and bottom MRZ pattern heuristic. Clamps confidence to `[0.0, 1.0]`.

### Module M3: Document OCR
* **Module Folder:** `backend/app/modules/m3_ocr`
* **Handler File:** `backend/app/modules/m3_ocr/handler.py`
* **Exact Entry Function:** 
  ```python
  def run(ingestion_out: Union[IngestionOutput, str], classifier_out: Union[ClassifierOutput, str]) -> OCROutput
  ```
* **Internal Execution:** Instantiates `DocumentOCR` in `ocr.py`. Calls PaddleOCR 3.7+ (`predict`). Passes recognized text lines and bounding boxes to `FieldExtractor` (`extractor.py`), which uses label anchors, separators, and document-specific heuristics to extract 6 target fields.

### Module M4: MRZ Parser + Cross-Check
* **Module Folder:** `backend/app/modules/m4_mrz`
* **Handler File:** `backend/app/modules/m4_mrz/handler.py`
* **Exact Entry Function:** 
  ```python
  def run(ingestion_out: IngestionOutput, ocr_out: OCROutput) -> MRZOutput
  ```
* **Internal Execution:** Detects MRZ text contour via OpenCV. Crops and performs dedicated Tesseract OCR pass. If image crop fails, falls back to parsing `ocr_out.raw_text`. Parses ICAO Doc 9303 TD3 (passport) and TD1 (ID card). Verifies 7-3-1 check digits and cross-checks against M3 OCR fields.

### Module M5: Rule Validation Engine
* **Module Folder:** `backend/app/modules/m5_rules`
* **Handler File:** `backend/app/modules/m5_rules/handler.py`
* **Exact Entry Function:** 
  ```python
  def run(ocr_out: OCROutput, mrz_out: MRZOutput) -> RuleValidationOutput
  ```
* **Internal Execution:** Prefers valid MRZ fields over OCR. Checks expiry date against `datetime.date.today()`. Validates issue date logic (`issue_date < expiry_date`, `issue_date <= today`, `issue_date >= dob`). Validates document number format. Formulates human-readable sentences in `flags`.

### Module M6: Tamper Detection Heuristic
* **Module Folder:** `backend/app/modules/m6_tamper`
* **Handler File:** `backend/app/modules/m6_tamper/handler.py`
* **Exact Entry Function:** 
  ```python
  def run(ingestion_out: IngestionOutput, ocr_out: OCROutput) -> TamperOutput
  ```
* **Internal Execution:** Computes 3 independent heuristics: Error Level Analysis (`ela.analyse`), ORB copy-move clone detection (`copy_move.analyse`), and character height variance (`font_consistency.analyse`). Averages scores into `suspicion_score` and caps flagged regions at 15.

### Module M7: Face Verification
* **Module Folder:** `backend/app/modules/m7_face`
* **Handler File:** `backend/app/modules/m7_face/handler.py`
* **Exact Entry Function:** 
  ```python
  def run(ingestion_out: IngestionOutput) -> FaceVerificationOutput
  ```
* **Internal Execution:** Calls `verify_faces(ingestion_out)` in `service.py`. Uses lazy-loaded InsightFace `FaceAnalysis` singleton. Crops primary face from document and live photo. Generates 512-dim ArcFace embeddings and calculates scaled cosine similarity `(dot + 1) / 2`. Maps to `confident_match`, `review`, or `likely_mismatch`.

### Module M8: Database / Blacklist Check
* **Module Folder:** `backend/app/modules/m8_db`
* **Handler File:** `backend/app/modules/m8_db/handler.py`
* **Exact Entry Function:** 
  ```python
  def run(mrz_out: MRZOutput, ocr_out: OCROutput) -> DBCheckOutput
  ```
* **Internal Execution:** Calls `check_database(mrz_out, ocr_out)` in `service.py`. Resolves document number (prefers valid MRZ doc number, falls back to OCR). Connects to MongoDB `blacklist` collection with a 2000ms fail-fast timeout. Returns `clean`, `blacklisted`, `watchlist`, `not_found`, or `db_unavailable`.

### Module M9: Risk Engine
* **Module Folder:** `backend/app/modules/m9_risk_engine`
* **Handler File:** `backend/app/modules/m9_risk_engine/handler.py`
* **Exact Entry Function:** 
  ```python
  def run(
      classifier_out: ClassifierOutput,
      ocr_out: OCROutput,
      mrz_out: MRZOutput,
      rules_out: RuleValidationOutput,
      tamper_out: TamperOutput,
      face_out: FaceVerificationOutput,
      db_out: DBCheckOutput,
  ) -> RiskEngineOutput
  ```
* **Internal Execution:** Normalizes 6 upstream risk signals to 0–1. Applies weights: `blacklist_hit` (0.30), `expired` (0.20), `ocr_mrz_mismatch` (0.15), `face_mismatch` (0.20), `tamper_suspicion` (0.10), `low_ocr_confidence` (0.05). Calculates integer `risk_score` (0–100). Sets band (`low`, `medium`, `high`). Formats top 3 explanatory reasons.

---

## 3. Exact Input/Output Schema of Every Module

All schemas are defined in `backend/app/schemas/contracts.py`:

```python
# M1 Ingestion Output
class IngestionOutput(BaseModel):
    session_id: str                          # UUID string
    doc_image_path: str                      # Normalized path to preprocessed document image
    live_photo_path: str                     # Normalized path to raw live photo
    doc_type_hint: Optional[str] = None      # Optional user/client hint

# M2 Classifier Output
class ClassifierOutput(BaseModel):
    doc_type: str                            # "passport" | "visa" | "id_card" | "unknown"
    doc_type_confidence: float               # 0.0 to 1.0
    doc_bbox: Optional[List[int]] = None     # [x, y, w, h] or None

# M3 OCR Output
class OCROutput(BaseModel):
    fields: Dict[str, str]                   # Keys: name, dob, doc_number, expiry_date, nationality, issue_date
    field_confidences: Dict[str, float]      # Per-field recognition confidence 0.0 to 1.0
    raw_text: str                            # Raw unformatted text extracted from document

# M4 MRZ Output
class MRZOutput(BaseModel):
    mrz_present: bool                        # True if MRZ zone detected and parsed
    mrz_fields: Dict[str, str]               # Parsed ICAO fields (doc_number, name, dob, expiry_date, etc.)
    checksum_valid: bool                     # True if all composite and individual check digits pass
    cross_check: Dict[str, bool]             # Keys: name_match, dob_match, doc_number_match, expiry_match

# M5 Rule Validation Output
class RuleValidationOutput(BaseModel):
    is_expired: bool                         # True if expiry_date < current date
    format_valid: bool                       # True if doc number and dates follow structural syntax
    logic_valid: bool                        # True if issue_date < expiry_date, dob plausible
    flags: List[str]                         # Human-readable reasons for failed rules

# M6 Tamper Output
class TamperOutput(BaseModel):
    suspicion_score: float                   # 0.0 to 1.0 composite suspicion
    flagged_regions: List[List[int]]         # Bounding boxes [x, y, w, h] of anomalous areas
    signals: Dict[str, float]                # Keys: ela_score, copy_move_score, font_inconsistency_score

# M7 Face Verification Output
class FaceVerificationOutput(BaseModel):
    similarity: float                        # 0.0 to 1.0 scaled cosine similarity
    match_band: str                          # "confident_match" | "review" | "likely_mismatch"
    liveness_passed: Optional[bool] = None   # None (stretch goal)

# M8 Database Check Output
class DBCheckOutput(BaseModel):
    status: str                              # "clean" | "blacklisted" | "watchlist" | "not_found" | "db_unavailable"
    record_meta: Optional[dict] = None       # Metadata dict from database record, or None

# M9 Risk Engine Output
class RiskEngineOutput(BaseModel):
    risk_score: int                          # 0 to 100
    risk_band: str                           # "low" | "medium" | "high"
    reasons: List[str]                       # Top 1-3 plain-English reasons for score
    contributions: Dict[str, float]          # Breakdown of weighted contributions
```

---

## 4. Exact M1 → M2 → ... → M9 Data Flow

```text
[HTTP POST /screen: doc_file, live_photo]
       │
       ▼ (doc_bytes, live_bytes)
[M1: Ingestion]
       │
       ▼ IngestionOutput (session_id, doc_image_path, live_photo_path)
       ├─────────────────────────────────────────┐
       ▼                                         ▼
[M2: Classifier]                          [M7: Face Verification]
       │                                         │
       ▼ ClassifierOutput (doc_type)             │
       ▼                                         │
[M3: OCR]                                        │
  (consumes IngestionOutput + ClassifierOutput)   │
       │                                         │
       ▼ OCROutput (fields, field_confidences, raw_text)
       ├──────────────────────┬──────────────────┤
       ▼                      ▼                  ▼
[M4: MRZ Parser]       [M5: Rules]        [M6: Tamper]
  (IngestionOutput +     (OCROutput +       (IngestionOutput +
   OCROutput)             MRZOutput)         OCROutput)
       │                      │                  │
       ▼ MRZOutput            ▼ RuleOutput       ▼ TamperOutput
       ├──────────────────────┘                  │
       ▼                                         │
[M8: Database]                                   │
  (MRZOutput + OCROutput)                        │
       │                                         │
       ▼ DBCheckOutput                           │
       ├─────────────────────────────────────────┘
       ▼
[M9: Risk Engine]
  (ClassifierOutput, OCROutput, MRZOutput, RuleValidationOutput, TamperOutput, FaceVerificationOutput, DBCheckOutput)
       │
       ▼ RiskEngineOutput (risk_score, risk_band, reasons, contributions)
       │
       ▼ Packaged into ScreeningResult
[HTTP 200 Response JSON]
```

---

## 5. Every Module-to-Module Incompatibility

### 1. Ingestion Interface Incompatibility (CRITICAL / BLOCKING)
* **Location:** `backend/app/orchestrator/pipeline.py` line 47 vs `backend/app/modules/m1_ingestion/handler.py` line 96.
* **Problem:** `pipeline.py` defines:
  ```python
  def pipeline(doc_file_path: str, live_photo_path: str):
      ingestion_out = m1_ingestion.run(doc_file_path, live_photo_path)
  ```
  `pipeline.py` passes file path strings (`str`). But `m1_ingestion.run()` has explicit type assertions:
  ```python
  if not isinstance(doc_image_bytes, bytes):
      raise TypeError("doc_image_bytes must be bytes")
  if not isinstance(live_photo_bytes, bytes):
      raise TypeError("live_photo_bytes must be bytes")
  ```
* **Impact:** Calling `pipeline.py` immediately throws an unhandled `TypeError` on line 108 of M1.
* **Resolution Without Rewriting Modules:** Allow `m1_ingestion/handler.py` to accept `Union[bytes, str]`. If `str`, read bytes with `open(path, 'rb').read()`. If `bytes`, use directly. Alternatively, ensure `pipeline.py` receives bytes from FastAPI and passes bytes to M1.

### 2. Orchestrator Return Tuple vs Frontend Expected Object (CRITICAL / BLOCKING)
* **Location:** `backend/app/orchestrator/pipeline.py` line 84 vs `frontend/app/types/contracts.ts` line 54.
* **Problem:** `pipeline.py` returns:
  ```python
  return risk_out, raw_outputs
  ```
  This is a Python 2-tuple `(RiskEngineOutput, Dict[str, Any])`. Serializing this returns a JSON array `[ {...risk...}, {...raw...} ]`. Furthermore, `raw_outputs` stores the ingestion output under `"ingestion"`, whereas the frontend expects a flat object with `session_id` at the root and `risk` as a sibling property.
* **Impact:** The frontend TypeScript contract `ScreeningResult` expects:
  ```typescript
  {
    session_id: string;
    classifier: ClassifierOutput;
    ocr: OCROutput;
    mrz: MRZOutput;
    rules: RuleValidationOutput;
    tamper: TamperOutput;
    face: FaceVerificationOutput;
    db: DBCheckOutput;
    risk: RiskEngineOutput;
  }
  ```
  Passing the orchestrator tuple causes Axios or the frontend UI to fail immediately with undefined property errors (`result.risk is undefined`, `result.session_id is undefined`).
* **Resolution:** The orchestrator or API layer must package the outputs into a single dictionary or Pydantic model matching `ScreeningResult`.

### 3. Module 4 Top-Level Import Blocked by Missing Dependency
* **Location:** `backend/app/modules/m4_mrz/handler.py` line 26.
* **Problem:** `import pytesseract` is at the top level of `m4_mrz/handler.py`. `pytesseract` is not installed in the active Python environment.
* **Impact:** Importing `backend.app.orchestrator.pipeline` or `backend.app.modules.m4_mrz.handler` crashes the entire backend with `ModuleNotFoundError: No module named 'pytesseract'`.
* **Resolution:** Install `pytesseract` via `pip install pytesseract`, and make the import defensive in `m4_mrz/handler.py` so the module falls back to `ocr_out.raw_text` if Tesseract is unavailable.

### 4. Module 8 Top-Level Import Blocked by Missing Dependency
* **Location:** `backend/app/modules/m8_db/service.py` line 26 and `connection.py` line 13.
* **Problem:** `from pymongo import MongoClient` is at the top level. `pymongo` is listed in `backend/requirements.txt` but not installed in the Python environment.
* **Impact:** Importing `m8_db.handler` crashes with `ModuleNotFoundError: No module named 'pymongo'`.
* **Resolution:** Install `pymongo` via `pip install pymongo`.

---

## 6. Existing Orchestrator / API Endpoints

### 1. Production API Entry Point: `backend/app/main.py`
* **Status:** **NON-EXISTENT / EMPTY STUB**
* **Contents:** Currently only 9 lines of comments with a `# TODO: Implement FastAPI app`. No FastAPI application instance exists, no routes are bound, and no server can be launched from `backend/app/main.py`.

### 2. Orchestrator: `backend/app/orchestrator/pipeline.py`
* **Status:** Implemented as a standalone function `pipeline(doc_file_path, live_photo_path)`.
* **Issue:** Cannot execute due to the M1 parameter type mismatch and the unhandled `pytesseract` import error.

### 3. Temporary Mock Server: `frontend/mock-api/main.py`
* **Status:** Fully functional mock FastAPI app created by P5 to test the frontend in isolation.
* **Exposed Routes:**
  * `POST /screen`: Accepts `doc_file`, `live_photo`, and `scenario` query parameter (`clean`, `blacklisted`, `expired`, `high_risk`). Returns mock `ScreeningResult`.
* **Disposition:** Used only for mock UI testing; must be superseded by the real backend API in `backend/app/main.py`.

---

## 7. Exact Backend Endpoint the Frontend Should Call

The frontend MUST call a single orchestration endpoint:

### **`POST http://localhost:8000/screen`**

* **Why Single Endpoint:** Document screening is an atomic, sequential pipeline. The frontend does not have the intermediate data to call M2, M3, etc. independently. A single `POST /screen` receives the two uploaded images, orchestrates all 9 modules on the backend, and returns the complete screening assessment.

---

## 8. Exact Frontend → Backend Request Contract

* **HTTP Method:** `POST`
* **Endpoint URL:** `http://localhost:8000/screen` (or `${process.env.NEXT_PUBLIC_API_BASE_URL}/screen`)
* **Content-Type:** `multipart/form-data`
* **Headers:** `Accept: application/json`
* **Form Data Fields:**
  1. `doc_file`: Binary file upload (JPG or PNG) — identity document.
  2. `live_photo`: Binary file upload (JPG or PNG) — applicant live photo / selfie.

### Raw HTTP Request Example:
```http
POST /screen HTTP/1.1
Host: localhost:8000
Content-Type: multipart/form-data; boundary=----WebKitFormBoundary7MA4YWxkTrZu0gW
Accept: application/json

------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="doc_file"; filename="passport_sample.jpg"
Content-Type: image/jpeg

[RAW BINARY IMAGE DATA]
------WebKitFormBoundary7MA4YWxkTrZu0gW
Content-Disposition: form-data; name="live_photo"; filename="selfie_sample.jpg"
Content-Type: image/jpeg

[RAW BINARY IMAGE DATA]
------WebKitFormBoundary7MA4YWxkTrZu0gW--
```

---

## 9. Exact Backend → Frontend Response Contract

The response must be HTTP `200 OK` returning a JSON body strictly conforming to `ScreeningResult`:

```json
{
  "session_id": "4a9f1b2c-8d3e-4a5f-9b1c-2d3e4a5f6b7c",
  "classifier": {
    "doc_type": "passport",
    "doc_type_confidence": 0.88,
    "doc_bbox": null
  },
  "ocr": {
    "fields": {
      "name": "SMITH JOHN",
      "dob": "1985-05-20",
      "doc_number": "P12345678",
      "expiry_date": "2030-01-01",
      "nationality": "USA",
      "issue_date": "2020-01-01"
    },
    "field_confidences": {
      "name": 0.96,
      "dob": 0.95,
      "doc_number": 0.99,
      "expiry_date": 0.97,
      "nationality": 0.99,
      "issue_date": 0.94
    },
    "raw_text": "PASSPORT\nUNITED STATES OF AMERICA\nP<USASMITH<<JOHN<<<<<<<<<<<<<<<<<<<\nP123456784USA8505201M3001018<<<<<<<"
  },
  "mrz": {
    "mrz_present": true,
    "mrz_fields": {
      "doc_number": "P12345678",
      "name": "SMITH JOHN",
      "dob": "1985-05-20",
      "expiry_date": "2030-01-01",
      "nationality": "USA"
    },
    "checksum_valid": true,
    "cross_check": {
      "name_match": true,
      "dob_match": true,
      "doc_number_match": true,
      "expiry_match": true
    }
  },
  "rules": {
    "is_expired": false,
    "format_valid": true,
    "logic_valid": true,
    "flags": []
  },
  "tamper": {
    "suspicion_score": 0.04,
    "flagged_regions": [],
    "signals": {
      "ela_score": 0.03,
      "copy_move_score": 0.01,
      "font_inconsistency_score": 0.08
    }
  },
  "face": {
    "similarity": 0.89,
    "match_band": "confident_match",
    "liveness_passed": null
  },
  "db": {
    "status": "clean",
    "record_meta": {
      "category": "regular_traveler",
      "verification_status": "verified"
    }
  },
  "risk": {
    "risk_score": 3,
    "risk_band": "low",
    "reasons": [
      "No significant risk factors detected"
    ],
    "contributions": {
      "blacklist_hit": 0.0,
      "expired": 0.0,
      "ocr_mrz_mismatch": 0.0,
      "face_mismatch": 0.022,
      "tamper_suspicion": 0.004,
      "low_ocr_confidence": 0.0
    }
  }
}
```

---

## 10. Every Frontend/Backend Mismatch

| Parameter / Feature | Frontend (`frontend/`) | Backend (`backend/`) | Mismatch Description | Required Fix |
| :--- | :--- | :--- | :--- | :--- |
| **API Server Route** | Calls `POST /screen` on port 8000 | `main.py` is empty | Backend route does not exist. Frontend requests fail with `ERR_CONNECTION_REFUSED`. | Implement FastAPI with `@app.post("/screen")` in `backend/app/main.py`. |
| **Response Format** | Expects single JSON object `ScreeningResult` | `pipeline.py` returns `Tuple[RiskEngineOutput, Dict]` | Tuple serializes to a JSON array `[risk, raw]`; frontend crashes reading properties. | In `main.py` / `pipeline.py`, return a flat dictionary or `ScreeningResult` object. |
| **Session ID** | Expects `session_id` at response root | In `pipeline.py`, `session_id` is inside `raw_outputs["ingestion"].session_id` | `result.session_id` is undefined in frontend dashboard. | Extract `session_id = ingestion_out.session_id` and place at the root of the response. |
| **Risk Object** | Expects `risk` at response root | In `pipeline.py`, `risk` is the first element of the tuple | `result.risk` is undefined in frontend dashboard. | Place `risk = risk_out` inside the root response object. |
| **Input Data Type** | Sends multipart `UploadFile` | `pipeline.py` expects string file paths | `pipeline.py` cannot accept `UploadFile` directly. | In `main.py`, read bytes via `await doc_file.read()` and pass bytes to the pipeline. |
| **Error Handling Format** | Expects `err.response.data.detail` | Unhandled exceptions return HTML 500 | Frontend displays generic or unhelpful error messages. | Add FastAPI exception handlers returning `{"detail": "..."}` with appropriate HTTP status codes. |

---

## 11. CORS / Configuration / Port Issues

1. **CORS Policy:**
   * Frontend runs on `http://localhost:3000`.
   * Backend runs on `http://localhost:8000`.
   * Browsers block cross-origin requests from `:3000` to `:8000` unless the backend explicitly emits CORS headers.
   * **Fix:** Add `CORSMiddleware` in `backend/app/main.py`:
     ```python
     app.add_middleware(
         CORSMiddleware,
         allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
         allow_credentials=True,
         allow_methods=["*"],
         allow_headers=["*"],
     )
     ```
2. **Missing Frontend Dependencies:**
   * `frontend/node_modules/` is missing.
   * Running `npm run dev` in `frontend` fails immediately.
   * **Fix:** Execute `npm install` in the `frontend` directory.
3. **Missing Python Packages:**
   * `fastapi`, `uvicorn`, `python-multipart`, `pymongo`, and `pytesseract` are not installed in the active Python environment.
   * **Fix:** Execute `python -m pip install fastapi uvicorn python-multipart pymongo pytesseract`.
4. **Environment Configuration File:**
   * Neither root nor `frontend/` contains an `.env` or `.env.local` file.
   * **Fix:** Create `frontend/.env.local` with `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.

---

## 12. Error-Handling Flow

```
                  ┌──────────────────────────────┐
                  │ Client Upload (UploadForm)   │
                  └──────────────┬───────────────┘
                                 │
                   Valid file?   ▼
                 ┌───────────────┴───────────────┐
                 │                               │
            No   ▼                          Yes  ▼
  ┌─────────────────────────────┐  ┌─────────────────────────────┐
  │ HTTP 400 Bad Request        │  │ M1: Ingestion               │
  │ {"detail": "Empty file..."} │  └──────────────┬──────────────┘
  └─────────────────────────────┘                 │
                                    OpenCV fails? ▼
                                   ┌──────────────┴──────────────┐
                                   │                             │
                              Yes  ▼                        No   ▼
                       ┌────────────────┐         ┌─────────────────────┐
                       │ Fallback to    │         │ Use preprocessed    │
                       │ doc_raw.jpg    │         │ doc_preprocessed.jpg│
                       └───────┬────────┘         └──────────┬──────────┘
                               │                             │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                                     ┌──────────────────┐
                                     │ M2: Classifier   │
                                     └────────┬─────────┘
                                              │
                              Low confidence? ▼
                             ┌────────────────┴────────────────┐
                             │                                 │
                        Yes  ▼                            No   ▼
                 ┌────────────────────────┐      ┌────────────────────────┐
                 │ Fallback to heuristic  │      │ Use MobileNetV3 class  │
                 │ (aspect ratio + MRZ)   │      └───────────┬────────────┘
                 └───────────┬────────────┘                  │
                             │                               │
                             └────────────────┬──────────────┘
                                              │
                                              ▼
                                     ┌──────────────────┐
                                     │ M3: OCR          │
                                     └────────┬─────────┘
                                              │
                              PaddleOCR fails?▼
                             ┌────────────────┴────────────────┐
                             │                                 │
                        Yes  ▼                            No   ▼
                 ┌────────────────────────┐      ┌────────────────────────┐
                 │ Empty fields + 0 conf  │      │ Extracted fields & conf│
                 └───────────┬────────────┘      └───────────┬────────────┘
                             │                               │
                             └────────────────┬──────────────┘
                                              │
                                              ▼
                                  ┌───────────────────────┐
                                  │ M4, M5, M6, M7, M8    │
                                  └───────────┬───────────┘
                                              │
                                              ▼
                                  ┌───────────────────────┐
                                  │ M9: Risk Engine       │
                                  └───────────┬───────────┘
                                              │
                                              ▼
                                  ┌───────────────────────┐
                                  │ ScreeningResult       │
                                  │ (HTTP 200 OK)         │
                                  └───────────────────────┘
```

* **Defensive Pipeline Guarantees:**
  * If M2 cannot classify the document, it outputs `doc_type="unknown"` without crashing.
  * If M3 fails to extract text, it outputs empty strings, which M5 cleanly flags.
  * If M4 cannot detect an MRZ, it returns `mrz_present=False` without crashing.
  * If M6 encounters an error in ELA, Copy-Move, or Font consistency, each signal catches its own exception and returns `0.0`.
  * If M7 cannot load InsightFace, it returns `similarity=0.0, match_band="likely_mismatch"` without crashing.
  * If M8 cannot reach MongoDB, it returns `status="db_unavailable"` within 2 seconds without hanging.
  * If any unhandled exception occurs in `main.py`, FastAPI catches it and returns HTTP 500 with a clean JSON detail.

---

## 13. Exact Files / Functions That Need Changes

To maintain code integrity and respect the rule that **existing module implementations must not be rewritten**, only the connection layer requires modification:

| File Path | Function / Scope | Change Required | Reason |
| :--- | :--- | :--- | :--- |
| `backend/app/main.py` | Entire File | **Implement FastAPI Application** | Currently an empty stub; needs `@app.post("/screen")`, CORS middleware, file reading, and exception handling. |
| `backend/app/schemas/contracts.py` | Bottom of File | **Append `ScreeningResult` Model** | Adds composite contract matching frontend TypeScript definition. |
| `backend/app/orchestrator/pipeline.py` | `pipeline()` function | **Update Parameter & Return Types** | Accept `bytes` (or `str`), pass to M1, assemble and return `ScreeningResult` object instead of a 2-tuple. |
| `backend/app/modules/m1_ingestion/handler.py` | `run()` function | **Accept `Union[bytes, str]`** | Allow both file paths and binary bytes so caller can pass either without `TypeError`. |
| `backend/app/modules/m4_mrz/handler.py` | Import block | **Defensive `pytesseract` Import** | Wrap `import pytesseract` in `try/except ImportError` so module doesn't crash if binary or package is absent. |
| `frontend/.env.local` | New File | **Create Environment File** | Define `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`. |

---

## 14. Priority Matrix (P0 / P1 / P2)

### P0 — Blocking (System Cannot Function Without These)
1. **Implement `backend/app/main.py`:** Create FastAPI app, CORS middleware, and `POST /screen` route.
2. **Install Core Backend Dependencies:** `fastapi`, `uvicorn`, `python-multipart`, `pymongo`.
3. **Fix Ingestion Parameter Mismatch:** Enable `m1_ingestion/handler.py` and `pipeline.py` to exchange bytes seamlessly.
4. **Fix Return Contract Shape:** Define `ScreeningResult` in `contracts.py` and return it from `pipeline.py`.
5. **Install Frontend Dependencies:** Run `npm install` in `frontend/`.
6. **Defensive Pytesseract Import:** Wrap `pytesseract` in `m4_mrz/handler.py` and install `pytesseract`.

### P1 — Required (Needed for Complete End-to-End System)
1. **Create `frontend/.env.local`:** Set `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`.
2. **Seed MongoDB Records:** Start MongoDB and execute `python -m backend.app.modules.m8_db.seed`.
3. **Install InsightFace & ONNXRuntime:** Enable real biometric face similarity comparison.
4. **Update `backend/requirements.txt`:** Add `python-multipart`, `pytesseract`, and `opencv-python`.

### P2 — Important (Improves Reliability, Maintenance, & Spec Alignment)
1. **Implement `POST /decision`:** Add officer audit decision endpoint to `main.py`.
2. **Add Decision Action Buttons in Frontend:** Add Approve / Deny / Escalate buttons to `ResultsDashboard.tsx`.
3. **Async Pipeline Optimization:** Run independent modules (M4/M5/M6 and M7/M8) concurrently using `asyncio.gather`.
4. **File Validation:** Add MIME-type and size validation in `POST /screen`.

---

## 15. Step-by-Step Implementation Plan

Follow this exact sequential plan to execute the integration:

### Step 1: Install Dependencies
Open PowerShell and run:
```powershell
# 1. Install missing Python dependencies
python -m pip install fastapi uvicorn python-multipart pymongo pytesseract

# 2. Install missing Node.js dependencies
cd frontend
npm install
cd ..
```

### Step 2: Append `ScreeningResult` to Backend Contracts
Edit `backend/app/schemas/contracts.py` and append at the end:
```python
class ScreeningResult(BaseModel):
    session_id: str
    classifier: ClassifierOutput
    ocr: OCROutput
    mrz: MRZOutput
    rules: RuleValidationOutput
    tamper: TamperOutput
    face: FaceVerificationOutput
    db: DBCheckOutput
    risk: RiskEngineOutput
```

### Step 3: Enable Flexible Input in M1 Ingestion Handler
In `backend/app/modules/m1_ingestion/handler.py`, update `run()` (lines 96–111) to accept either `bytes` or `str`:
```python
def run(
    doc_image_bytes: Union[bytes, str],
    live_photo_bytes: Union[bytes, str],
    doc_type_hint: Optional[str] = None
) -> IngestionOutput:
    if isinstance(doc_image_bytes, str):
        with open(doc_image_bytes, "rb") as f:
            doc_image_bytes = f.read()
    if isinstance(live_photo_bytes, str):
        with open(live_photo_bytes, "rb") as f:
            live_photo_bytes = f.read()

    if not isinstance(doc_image_bytes, bytes):
        raise TypeError("doc_image_bytes must be bytes or valid file path")
    if not isinstance(live_photo_bytes, bytes):
        raise TypeError("live_photo_bytes must be bytes or valid file path")
    ...
```

### Step 4: Protect Pytesseract Import in M4 MRZ Handler
In `backend/app/modules/m4_mrz/handler.py`, wrap line 26:
```python
try:
    import pytesseract
except ImportError:
    pytesseract = None
```
In `_ocr_mrz_region()` (line 239), check:
```python
if pytesseract is None:
    raise RuntimeError("pytesseract is not installed")
```

### Step 5: Update Orchestrator Pipeline
In `backend/app/orchestrator/pipeline.py`, update `pipeline()` to return `ScreeningResult`:
```python
from typing import Any, Dict, Union
from backend.app.schemas.contracts import ScreeningResult

def pipeline(doc_input: Union[bytes, str], live_input: Union[bytes, str]) -> ScreeningResult:
    # M1 Ingestion & Preprocessing
    ingestion_out = m1_ingestion.run(doc_input, live_input)

    # Document Understanding (M2 Classifier + M3 OCR)
    classifier_out = m2_classifier.run(ingestion_out)
    ocr_out = m3_ocr.run(ingestion_out, classifier_out)

    # Document Integrity (M4 MRZ + M5 Rules + M6 Tamper)
    mrz_out = m4_mrz.run(ingestion_out, ocr_out)
    rules_out = m5_rules.run(ocr_out, mrz_out)
    tamper_out = m6_tamper.run(ingestion_out, ocr_out)

    # Identity & Records (M7 Face Verification + M8 Database Check)
    face_out = m7_face.run(ingestion_out)
    db_out = m8_db.run(mrz_out, ocr_out)

    # M9 Risk Decision Engine
    risk_out = m9_risk_engine.run(
        classifier_out,
        ocr_out,
        mrz_out,
        rules_out,
        tamper_out,
        face_out,
        db_out,
    )

    return ScreeningResult(
        session_id=ingestion_out.session_id,
        classifier=classifier_out,
        ocr=ocr_out,
        mrz=mrz_out,
        rules=rules_out,
        tamper=tamper_out,
        face=face_out,
        db=db_out,
        risk=risk_out,
    )

run = pipeline
```

### Step 6: Implement FastAPI Application Entry Point
In `backend/app/main.py`, write the complete FastAPI application:
```python
import logging
from typing import Optional
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.app.orchestrator.pipeline import pipeline
from backend.app.schemas.contracts import ScreeningResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("screening-api")

app = FastAPI(
    title="AI Document Screening API",
    description="Automated document verification and risk screening system.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "ai-document-screening"}

@app.post("/screen", response_model=ScreeningResult)
async def screen_document(
    doc_file: UploadFile = File(...),
    live_photo: UploadFile = File(...),
    doc_type_hint: Optional[str] = None,
):
    if not doc_file.filename or not live_photo.filename:
        raise HTTPException(status_code=400, detail="Both doc_file and live_photo must be provided.")

    try:
        doc_bytes = await doc_file.read()
        live_bytes = await live_photo.read()
    except Exception as exc:
        logger.error(f"Error reading file bytes: {exc}")
        raise HTTPException(status_code=400, detail="Failed to read uploaded file contents.")

    if len(doc_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded document file is empty.")
    if len(live_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded live photo file is empty.")

    try:
        result = pipeline(doc_bytes, live_bytes)
        return result
    except Exception as exc:
        logger.exception("Pipeline execution failed")
        raise HTTPException(status_code=500, detail=f"Screening pipeline error: {str(exc)}")

class OfficerDecision(BaseModel):
    session_id: str
    decision: str
    officer_id: Optional[str] = "OFFICER-001"
    notes: Optional[str] = None

@app.post("/decision")
def record_decision(payload: OfficerDecision):
    logger.info(f"Officer decision: {payload.decision} on session {payload.session_id}")
    return {"status": "recorded", "session_id": payload.session_id, "decision": payload.decision}
```

### Step 7: Configure Frontend Environment
Create `frontend/.env.local`:
```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

### Step 8: End-to-End System Verification
1. **Terminal 1 (Backend):**
   ```powershell
   uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
2. **Terminal 2 (Frontend):**
   ```powershell
   cd frontend
   npm run dev
   ```
3. Open `http://localhost:3000` in the browser.
4. Upload `test_images/personA1.png` as document and `test_images/personA1.png` as live photo.
5. Click **"Screen Document"**.
6. Verify the dashboard displays the risk score, verification badges (MRZ, Rules, Face, DB), and extracted OCR fields.
