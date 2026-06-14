"use client";

import type { ImageResult, Summary } from "../lib/types";

interface Props {
  summary: Summary;
  results: ImageResult[];
  onSelect: (index: number) => void;
}

export default function ResultsGrid({ summary, results, onSelect }: Props) {
  return (
    <div>
      <div className="summary">
        <span className="chip total">{summary.total} total</span>
        <span className="chip PASS">{summary.passed} pass</span>
        <span className="chip WARN">{summary.warned} warn</span>
        <span className="chip FAIL">{summary.failed} fail</span>
      </div>

      <div className="results-grid">
        {results.map((r, i) => (
          <div
            key={i}
            className={`card result-card ${r.verdict}`}
            onClick={() => onSelect(i)}
          >
            <div className="filename">{r.filename}</div>
            <span className={`verdict ${r.verdict}`}>{r.verdict}</span>
            <div className="meta">
              {r.findings.length} finding{r.findings.length === 1 ? "" : "s"} ·{" "}
              {r.timings.total_ms}ms
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
