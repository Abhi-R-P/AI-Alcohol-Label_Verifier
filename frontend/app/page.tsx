"use client";

import { useState } from "react";
import { uploadLabels } from "../lib/api";
import LabelResult from "../components/LabelResult";
import type { ImageResult } from "../lib/types";

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
          <LabelResult key={i} result={result} />
        ))}
      </div>
    </main>
  );
}
