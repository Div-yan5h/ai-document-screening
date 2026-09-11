# Technology Stack

> All technologies listed here are explicitly specified or suggested by the
> [Build Spec](sih_build_spec.md). Nothing has been added beyond what the spec states.

---

## Backend

| Area | Technology | Where Used (Build Spec Reference) |
|------|-----------|-----------------------------------|
| **API Framework** | **FastAPI** | `main.py` — exposes `POST /screen` and `POST /decision` endpoints (§0, §3 M1, §3 M10) |
| **Contracts / Validation** | **Pydantic** (BaseModel) | `contracts.py` — frozen I/O models shared across all modules (§2) |
| **Async Parallelism** | **asyncio** (`asyncio.gather`) | Orchestrator — optional parallel execution of independent module groups M4/M5/M6 and M7/M8 (§4) |
| **ASGI Server** | **Uvicorn** | Serves the FastAPI application (implied by FastAPI) |

## Image Processing

| Area | Technology | Where Used |
|------|-----------|------------|
| **Preprocessing** | **OpenCV** | M1 — grayscale, deskew (Hough transform / `minAreaRect`), denoise (`fastNlMeansDenoising`), contrast enhance (CLAHE) (§3 M1) |
| **Tamper Detection** | **OpenCV** | M6 — Error Level Analysis (ELA via JPEG re-save + diff), copy-move detection (ORB or SIFT keypoints), font/spacing statistics (§3 M6) |
| **MRZ Zone Detection** | **OpenCV** | M4 — crop MRZ zone via text-line detection (§3 M4) |

## OCR

| Area | Technology | Where Used |
|------|-----------|------------|
| **General OCR** | **PaddleOCR** | M3 — extract raw text + bounding boxes from preprocessed document image, per-box confidence scores (§3 M3) |
| **MRZ OCR** | **Separate OCR pass** (on cropped MRZ zone) | M4 — dedicated OCR of MRZ lines, parsed per ICAO Doc 9303 format (§3 M4) |

## Document Classification

| Area | Technology | Where Used |
|------|-----------|------------|
| **Primary** | **YOLO** (classification head) or **lightweight CNN** (transfer learning off **MobileNet** / **ResNet18**) | M2 — whole-image classification into passport / visa / id_card / unknown (§3 M2) |
| **Fallback** | Rule-based heuristic (aspect ratio + MRZ text presence) | M2 — demo safety fallback if model training doesn't converge (§3 M2) |

## MRZ Processing

| Area | Technology | Where Used |
|------|-----------|------------|
| **Parsing Standard** | **ICAO Doc 9303** format | M4 — fixed-width field parsing and built-in checksum digit verification (§3 M4) |

## Rule Validation

| Area | Technology | Where Used |
|------|-----------|------------|
| **Logic** | Pure Python (deterministic checks) | M5 — expiry check, logical consistency, format validation, human-readable flag generation (§3 M5) |

## Tamper Detection

| Area | Technology | Where Used |
|------|-----------|------------|
| **ELA** | OpenCV (JPEG re-save + diff) | M6 — `ela_score` (§3 M6) |
| **Copy-Move** | OpenCV (**ORB** or **SIFT** keypoint matching) | M6 — `copy_move_score` (§3 M6) |
| **Font Consistency** | Statistical analysis on OCR bounding boxes | M6 — `font_inconsistency_score` (§3 M6) |

## Face Verification

| Area | Technology | Where Used |
|------|-----------|------------|
| **Face Detection** | **RetinaFace** or **MTCNN** | M7 — detect and crop face from document photo and live photo (§3 M7) |
| **Face Embeddings** | **ArcFace** / **InsightFace** | M7 — generate face embeddings, compute cosine similarity (§3 M7) |

## Database

| Area | Technology | Where Used |
|------|-----------|------------|
| **Document Store** | **MongoDB** | M8 — blacklist/watchlist collection, queried by `doc_number`, seeded with synthetic records (§3 M8) |

## Frontend

| Area | Technology | Where Used |
|------|-----------|------------|
| **Framework** | **Next.js** | Officer dashboard — upload UI, results display with risk breakdown, Approve/Deny/Escalate actions (§0, §3 M10) |

## Inter-Module Communication

| Mechanism | Description |
|-----------|-------------|
| **Pydantic contracts** | Every module exposes `def run(input) -> Output`. The orchestrator wires outputs → inputs. Modules never access each other's internals. (§0, §2, §4) |
| **JSON serialization** | Pydantic models serialize to/from JSON — the shared data format (§2) |

---

## Module → Technology Map

| Module | Name | Key Technologies |
|--------|------|-----------------|
| **M1** | Ingestion & Preprocessing | FastAPI, OpenCV |
| **M2** | Document Classifier | YOLO / MobileNet / ResNet18 (transfer learning) |
| **M3** | OCR | PaddleOCR |
| **M4** | MRZ Parser + Cross-Check | OpenCV, ICAO Doc 9303 |
| **M5** | Rule Validation | Pure Python (deterministic logic) |
| **M6** | Tamper Heuristic | OpenCV (ELA, ORB/SIFT) |
| **M7** | Face Verification | RetinaFace/MTCNN, ArcFace/InsightFace |
| **M8** | DB / Blacklist Check | MongoDB |
| **M9** | Risk Engine | Pure Python (weighted scoring) |
| **M10** | Officer Dashboard | Next.js |

---

## Runtime / Development Requirements (from Build Spec)

- **Python** — all backend modules
- **Pydantic ≥ 2.0** — frozen contracts
- **FastAPI** — API layer
- **Node.js / npm** — Next.js frontend
- **MongoDB** — blacklist/watchlist database
- **asyncio** — optional parallel module execution in the orchestrator
