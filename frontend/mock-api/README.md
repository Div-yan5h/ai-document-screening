# P5 Frontend Temporary Mock API

This directory contains a temporary mock FastAPI server strictly for end-to-end testing of the P5 Next.js frontend prior to integration with P1's production orchestrator.

## Quick Start Instructions

### Terminal 1: Run Mock Backend
```bash
cd frontend/mock-api
pip install fastapi uvicorn python-multipart

# Set test scenario (clean, blacklisted, expired, face_mismatch, high_risk)
set MOCK_SCENARIO=clean

# Launch mock server
uvicorn main:app --reload --port 8000
```

- API Base URL: `http://localhost:8000`
- Swagger Documentation: `http://localhost:8000/docs`

### Terminal 2: Run Next.js Frontend
```bash
cd frontend
npm run dev
```

- Next.js Officer Portal: `http://localhost:3000`

## Supported Scenarios (`MOCK_SCENARIO` environment variable)
- `clean` (Default): Low risk (2/100), clean database status
- `blacklisted`: Medium risk (30/100), blacklisted database status
- `expired`: Expired document flag & reason
- `face_mismatch`: Face similarity at 20%
- `high_risk`: High risk (95/100), multiple risk factors activated
