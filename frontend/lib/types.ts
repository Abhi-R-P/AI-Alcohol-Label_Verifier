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
  ocr_confidence: number;
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

export interface VerifyResponse {
  summary: Summary;
  results: ImageResult[];
}

export interface Profile {
  brand_name?: string;
  abv_percent?: number;
  net_contents?: string;
  region?: string;
}
