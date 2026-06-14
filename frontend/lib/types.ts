// Mirror of the backend Pydantic schemas (app/schemas.py).

export type Verdict = "PASS" | "WARN" | "FAIL";
export type Severity = "error" | "warn" | "info";

export interface LabelExtraction {
  brand_name: string | null;
  class_type: string | null;
  abv: number | null;
  net_contents: string | null;
  producer: string | null;
  government_warning: boolean;
}

export interface FieldResult {
  passed: boolean;
  reason: string | null;
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
  findings: Finding[];
  field_validation: Record<string, FieldResult>;
  timings: Timings;
  error: string | null;
}
