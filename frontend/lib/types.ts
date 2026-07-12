// Mirror of the backend Pydantic schemas (app/schemas.py).

export type Verdict = "PASS" | "WARN" | "FAIL";
export type FieldStatus = "pass" | "warn" | "fail" | "info";
export type Severity = "error" | "warn" | "info";

export interface LabelExtraction {
  brand_name: string | null;
  class_type: string | null;
  abv: number | null;
  net_contents: string | null;
  bottler_name: string | null;
  bottler_address: string | null;
  country_of_origin: string | null;
  government_warning_text: string | null;
}

export interface FieldResult {
  status: FieldStatus;
  reason: string | null;
  extracted: string | null;
  expected: string | null;
}

export interface Finding {
  code: string;
  severity: Severity;
  message: string;
}

export interface Timings {
  ocr_ms: number;
  claude_ms: number;
  rules_ms: number;
  total_ms: number;
}

export interface ImageResult {
  filename: string;
  verdict: Verdict;
  fields: LabelExtraction;
  ocr_text: string;
  ocr_confidence: number;
  field_validation: Record<string, FieldResult>;
  findings: Finding[];
  timings: Timings;
  error: string | null;
}

export interface Summary {
  total: number;
  passed: number;
  warned: number;
  failed: number;
}

// Expected values from the COLA application (all optional).
export interface ApplicationData {
  brand_name?: string;
  class_type?: string;
  abv?: number;
  net_contents?: string;
  bottler_name?: string;
  bottler_address?: string;
  country_of_origin?: string;
}
