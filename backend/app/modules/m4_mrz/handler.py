"""
M4 — MRZ Parser + Cross-Check (STUB)
=====================================
Walking skeleton stub. Returns mock MRZOutput.
Real implementation will: crop MRZ zone, OCR it, parse ICAO 9303, cross-check.

Owner: P3
"""

from backend.app.schemas.contracts import IngestionOutput, MRZOutput, OCROutput


def run(ingestion_out: IngestionOutput, ocr_out: OCROutput) -> MRZOutput:
    """
    STUB: Returns mock MRZOutput.

    Real implementation will:
    - Crop MRZ zone from ingestion_out.doc_image_path (OpenCV)
    - OCR the MRZ zone separately
    - Parse per ICAO Doc 9303, verify checksums
    - Cross-check MRZ fields against ocr_out fields
    """
    return MRZOutput(
        mrz_present=False,                        # STUB: no MRZ detected
        mrz_fields={},                            # STUB: empty
        checksum_valid=False,                     # STUB: no checksum to validate
        cross_check={},                           # STUB: no cross-check performed
    )
