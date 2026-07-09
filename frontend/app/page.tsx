"use client";

import { useEffect, useState } from "react";
import { uploadLabels } from "../lib/api";
import LabelResult from "../components/LabelResult";
import type { ApplicationData, ImageResult } from "../lib/types";

const APP_FIELDS: { key: keyof ApplicationData; label: string; placeholder: string }[] = [
  { key: "brand_name", label: "Brand name", placeholder: "Old Mill IPA" },
  { key: "class_type", label: "Class / type", placeholder: "IPA" },
  { key: "abv", label: "ABV %", placeholder: "6.5" },
  { key: "net_contents", label: "Net contents", placeholder: "355 mL" },
  { key: "bottler_name", label: "Bottler name", placeholder: "Old Mill Brewing Co." },
  { key: "bottler_address", label: "Bottler address", placeholder: "Portland, OR" },
  { key: "country_of_origin", label: "Country of origin", placeholder: "USA" },
];

export default function Home() {
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [results, setResults] = useState<ImageResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const urls = files.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [files]);

  function addFiles(list: FileList | null) {
    if (!list) return;
    const imgs = Array.from(list).filter((f) => f.type.startsWith("image/"));
    setFiles((prev) => [...prev, ...imgs]);
    setResults([]);
    setError(null);
  }

  function removeFile(i: number) {
    setFiles((prev) => prev.filter((_, idx) => idx !== i));
  }

  function reset() {
    setFiles([]);
    setCsvFile(null);
    setForm({});
    setResults([]);
    setError(null);
  }

  function buildApplication(): ApplicationData {
    const app: ApplicationData = {};
    for (const { key } of APP_FIELDS) {
      const v = form[key]?.trim();
      if (!v) continue;
      if (key === "abv") {
        const n = Number(v);
        if (!Number.isNaN(n)) app.abv = n;
      } else {
        (app as Record<string, string>)[key] = v;
      }
    }
    return app;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) return;
    setLoading(true);
    setError(null);
    setResults([]);
    try {
      setResults(await uploadLabels(files, buildApplication(), csvFile));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-5 py-12">
      <header className="mb-8 flex items-center gap-4">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/logo.png"
          alt="DOT — Alcohol and Tobacco Tax and Trade Bureau"
          className="h-20 w-auto flex-none object-contain"
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
        />
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-blue-600 dark:text-sky-400">
            AI Alcohol Label Verifier
          </h1>
          <p className="mt-2 text-slate-500">
            Upload label images — each is read with OCR, structured by Claude, and checked
            against TTB compliance rules and (optionally) your application data.
          </p>
        </div>
      </header>

      <form onSubmit={handleSubmit}>
        {/* Drag-and-drop / browse. */}
        <label
          htmlFor="label-files"
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            addFiles(e.dataTransfer.files);
          }}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-6 py-10 text-center transition ${
            dragging ? "border-slate-900 bg-slate-50" : "border-slate-300 bg-white hover:bg-slate-50"
          }`}
        >
          <span className="text-sm font-medium text-slate-700">
            Drag &amp; drop label images here, or <span className="underline">browse</span>
          </span>
          <span className="mt-1 text-xs text-slate-400">PNG, JPEG, or WebP — up to 10 files</span>
          <input
            id="label-files"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            multiple
            onChange={(e) => addFiles(e.target.files)}
            className="sr-only"
          />
        </label>

        {/* Thumbnails. */}
        {files.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-3">
            {files.map((file, i) => (
              <div key={i} className="relative">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={previews[i]} alt={file.name} className="h-20 w-20 rounded-lg object-cover ring-1 ring-slate-200" />
                <button
                  type="button"
                  onClick={() => removeFile(i)}
                  aria-label={`Remove ${file.name}`}
                  className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-xs font-bold text-white shadow"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Expected application values (optional). */}
        <details className="mt-4 rounded-xl border border-slate-200 bg-white p-4">
          <summary className="cursor-pointer text-sm font-medium text-slate-700">
            Expected values from the COLA application (optional)
          </summary>
          <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {APP_FIELDS.map(({ key, label, placeholder }) => (
              <label key={key} className="block text-xs font-medium text-slate-500">
                {label}
                <input
                  type={key === "abv" ? "number" : "text"}
                  step={key === "abv" ? "0.1" : undefined}
                  value={form[key] ?? ""}
                  placeholder={placeholder}
                  onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
                  className="mt-1 w-full rounded-md border border-slate-300 px-2.5 py-1.5 text-sm text-slate-800"
                />
              </label>
            ))}
          </div>
          <div className="mt-4 border-t border-slate-100 pt-3">
            <label className="block text-xs font-medium text-slate-500">
              Or upload a CSV of expected values (batch — columns: filename, brand_name, class_type, abv, net_contents, bottler_name, bottler_address, country_of_origin)
              <input
                type="file"
                accept=".csv,text/csv"
                onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)}
                className="mt-1 block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-200 file:px-3 file:py-1.5 file:text-sm file:font-medium"
              />
            </label>
            {csvFile && <p className="mt-1 text-xs text-slate-500">CSV: {csvFile.name}</p>}
          </div>
        </details>

        <div className="mt-5 flex items-center gap-3">
          <button
            type="submit"
            disabled={loading || files.length === 0}
            aria-busy={loading}
            className="rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-700 disabled:opacity-40"
          >
            {loading ? "Verifying…" : `Verify ${files.length || ""} label${files.length === 1 ? "" : "s"}`.trim()}
          </button>
          {(files.length > 0 || results.length > 0) && (
            <button
              type="button"
              onClick={reset}
              className="rounded-lg px-3 py-2.5 text-sm font-medium text-slate-500 hover:text-slate-800"
            >
              Reset
            </button>
          )}
        </div>
      </form>

      {error && (
        <div role="alert" className="mt-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && (
        <div className="mt-8 space-y-4" aria-hidden>
          {Array.from({ length: Math.max(files.length, 1) }).map((_, i) => (
            <div key={i} className="h-40 animate-pulse rounded-2xl bg-slate-100" />
          ))}
        </div>
      )}

      <div className="mt-8 space-y-4" aria-live="polite">
        {!loading && results.length > 0 && (
          <h2 className="sr-only">{results.length} label result{results.length > 1 ? "s" : ""}</h2>
        )}
        {!loading &&
          results.map((result, i) => (
            <LabelResult key={i} result={result} thumbnail={previews[i]} />
          ))}
      </div>
    </main>
  );
}
