"use client";

import { useState } from "react";
import { uploadLabels } from "../lib/api";
import type { ImageResult, Verdict } from "../lib/types";

const VERDICT_STYLES: Record<Verdict, string> = {
  PASS: "bg-green-100 text-green-800",
  WARN: "bg-amber-100 text-amber-800",
  FAIL: "bg-red-100 text-red-800",
};

const FIELD_LABELS: Record<string, string> = {
  government_warning: "Government warning",
  abv: "ABV",
  brand_name: "Brand name",
  class_type: "Class / type",
  net_contents: "Net contents",
  producer: "Producer",
};

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [results, setResults] = useState<ImageResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) return;
    setLoading(true);
    setError(null);
    setResults([]);
    try {
      setResults(await uploadLabels(files));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-5 py-10">
      <h1 className="text-2xl font-bold text-slate-900">AI Alcohol Label Verifier</h1>
      <p className="mt-1 text-sm text-slate-500">
        Upload one or more label images — each is OCR&apos;d, structured by Claude, and
        checked against the compliance rules.
      </p>

      <form onSubmit={handleSubmit} className="mt-6 rounded-xl border border-slate-200 bg-white p-5">
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          multiple
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          className="block w-full text-sm text-slate-600 file:mr-4 file:rounded-md file:border-0 file:bg-slate-900 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-slate-700"
        />
        <div className="mt-3 flex items-center justify-between">
          <span className="text-xs text-slate-500">
            {files.length > 0
              ? `${files.length} file${files.length > 1 ? "s" : ""} selected`
              : "No files selected"}
          </span>
          <button
            type="submit"
            disabled={loading || files.length === 0}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
          >
            {loading ? "Verifying…" : "Verify labels"}
          </button>
        </div>
      </form>

      {error && (
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="mt-6 space-y-4">
        {results.map((result, i) => (
          <ResultCard key={i} result={result} />
        ))}
      </div>
    </main>
  );
}

function ResultCard({ result }: { result: ImageResult }) {
  const entries = Object.entries(result.field_validation);
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h2 className="truncate font-semibold text-slate-900">{result.filename}</h2>
        <span
          className={`rounded-full px-3 py-1 text-xs font-bold ${VERDICT_STYLES[result.verdict]}`}
        >
          {result.verdict}
        </span>
      </div>

      {result.error && (
        <p className="mt-2 text-sm text-red-600">Note: {result.error}</p>
      )}

      <ul className="mt-3 divide-y divide-slate-100">
        {entries.map(([field, res]) => (
          <li key={field} className="flex items-start gap-3 py-2">
            <span className={res.passed ? "text-green-600" : "text-red-600"}>
              {res.passed ? "✓" : "✗"}
            </span>
            <div className="text-sm">
              <span className="font-medium text-slate-800">
                {FIELD_LABELS[field] ?? field}
              </span>
              <span className={res.passed ? "ml-2 text-green-700" : "ml-2 text-red-700"}>
                {res.passed ? "PASS" : "FAIL"}
              </span>
              {!res.passed && res.reason && (
                <p className="text-slate-500">{res.reason}</p>
              )}
            </div>
          </li>
        ))}
      </ul>

      <p className="mt-3 text-xs text-slate-400">
        OCR confidence {result.ocr_confidence.toFixed(0)} · {result.timings.total_ms}ms
      </p>
    </div>
  );
}
