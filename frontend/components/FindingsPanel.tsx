"use client";

import type { ImageResult } from "../lib/types";

interface Props {
  result: ImageResult;
  onClose: () => void;
}

function fmt(value: string | number | boolean | null): string {
  if (value === null || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

export default function FindingsPanel({ result, onClose }: Props) {
  const f = result.fields;
  return (
    <div className="card panel">
      <button className="close" onClick={onClose}>
        ← Back to results
      </button>
      <h2 style={{ margin: "0.5rem 0" }}>
        {result.filename}{" "}
        <span className={`verdict ${result.verdict}`}>{result.verdict}</span>
      </h2>

      <h3 style={{ fontSize: "0.95rem", marginBottom: 0 }}>Extracted fields</h3>
      <dl>
        <dt>Brand</dt>
        <dd>{fmt(f.brand_name)}</dd>
        <dt>Producer</dt>
        <dd>{fmt(f.producer)}</dd>
        <dt>Type</dt>
        <dd>{fmt(f.alcohol_type)}</dd>
        <dt>ABV</dt>
        <dd>{f.abv_percent === null ? "—" : `${f.abv_percent}%`}</dd>
        <dt>Net contents</dt>
        <dd>{fmt(f.net_contents)}</dd>
        <dt>Country of origin</dt>
        <dd>{fmt(f.country_of_origin)}</dd>
        <dt>Gov. warning</dt>
        <dd>{fmt(f.government_warning_present)}</dd>
        <dt>OCR confidence</dt>
        <dd>{result.ocr_confidence.toFixed(0)} / 100</dd>
      </dl>

      <h3 style={{ fontSize: "0.95rem", marginBottom: "0.5rem" }}>
        Findings ({result.findings.length})
      </h3>
      {result.findings.length === 0 ? (
        <p className="meta">No issues found — all rules passed.</p>
      ) : (
        result.findings.map((finding, i) => (
          <div key={i} className={`finding ${finding.severity}`}>
            <code>{finding.code}</code> — {finding.message}
          </div>
        ))
      )}

      <p className="meta">
        Timings — OCR {result.timings.ocr_ms}ms · Claude {result.timings.claude_ms}ms ·
        rules {result.timings.rules_ms}ms · total {result.timings.total_ms}ms
      </p>
    </div>
  );
}
