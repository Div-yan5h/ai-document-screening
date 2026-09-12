// TypeScript interfaces matching backend/app/schemas/contracts.py
// DO NOT modify these without updating the backend contracts first

export interface ClassifierOutput {
  doc_type: string;
  doc_type_confidence: number;
  doc_bbox: number[] | null;
}

export interface OCROutput {
  fields: Record<string, string>;
  field_confidences: Record<string, number>;
  raw_text: string;
}

export interface MRZOutput {
  mrz_present: boolean;
  mrz_fields: Record<string, string>;
  checksum_valid: boolean;
  cross_check: Record<string, boolean>;
}

export interface RuleValidationOutput {
  is_expired: boolean;
  format_valid: boolean;
  logic_valid: boolean;
  flags: string[];
}

export interface TamperOutput {
  suspicion_score: number;
  flagged_regions: number[][];
  signals: Record<string, number>;
}

export interface FaceVerificationOutput {
  similarity: number;
  match_band: string;
  liveness_passed: boolean | null;
}

export interface DBCheckOutput {
  status: string;
  record_meta: Record<string, any> | null;
}

export interface RiskEngineOutput {
  risk_score: number;
  risk_band: string;
  reasons: string[];
  contributions: Record<string, number>;
}

export interface ScreeningResult {
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
