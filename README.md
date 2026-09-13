# AI Document Screening System

**SIH 2026 — Team AIGES**

An AI-powered document screening pipeline for immigration officers that verifies travel documents (passports, visas, ID cards) through multi-stage analysis: document classification, OCR, MRZ verification, rule validation, tamper detection, face matching, and risk scoring.

---

## Repository Structure

```
backend/
  app/
    schemas/
      contracts.py        ← Frozen Pydantic I/O contracts (source of truth)
    modules/
      m1_ingestion/        → Ingestion & Preprocessing (P1)
      m2_classifier/       → Document Classifier (P2)
      m3_ocr/              → OCR Field Extraction (P2)
      m4_mrz/              → MRZ Parser + Cross-Check (P3)
      m5_rules/            → Rule Validation (P3)
      m6_tamper/           → Tamper Heuristic (P3)
      m7_face/             → Face Verification (P4)
      m8_db/               → DB / Blacklist Check (P4)
      m9_risk_engine/      → Risk Engine (P5)
    orchestrator/
      pipeline.py          ← Calls modules in order, wires outputs → inputs (P1)
    main.py                ← FastAPI app entry point (P1)
frontend/                  ← Next.js Officer Dashboard (P5)
```

## Team Split

| Person | Modules | Role |
|--------|---------|------|
| **P1** | M1 + Orchestrator + FastAPI | Platform Lead |
| **P2** | M2 + M3 | Document Understanding |
| **P3** | M4 + M5 + M6 | Document Integrity |
| **P4** | M7 + M8 | Identity & Records |
| **P5** | M9 + Frontend | Risk & Experience |

## Core Rule

> **Nobody touches another module's internals — everyone codes to the frozen contracts in `contracts.py`.**

Each module exposes **one function**: `def run(input) -> ModuleOutput`. The orchestrator only ever calls `run()`.

## Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux (or venv\Scripts\activate on Windows)

# Install dependencies
pip install -r backend/requirements.txt
```

## Running the Application

> **Note**: The backend must be running before performing document screening in the frontend.

### 1. Start the Backend (FastAPI)
```bash
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```
Backend API will run at `http://127.0.0.1:8000` (Health check: `http://127.0.0.1:8000/health`).

### 2. Start the Frontend (Next.js)
```bash
cd frontend
npm install
npm run dev
```
Then open your browser at:
`http://localhost:3000`

## Build Spec

See [`sih_build_spec.md`](sih_build_spec.md) for the complete build specification.

