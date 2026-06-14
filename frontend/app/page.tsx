"use client";

import { useState } from "react";
import UploadForm from "../components/UploadForm";
import ResultsGrid from "../components/ResultsGrid";
import FindingsPanel from "../components/FindingsPanel";
import { verifyImages } from "../lib/api";
import type { Profile, VerifyResponse } from "../lib/types";

export default function Home() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<VerifyResponse | null>(null);
  const [selected, setSelected] = useState<number | null>(null);

  async function handleSubmit(files: File[], profile: Profile) {
    setLoading(true);
    setError(null);
    setSelected(null);
    setData(null);
    try {
      const result = await verifyImages(files, profile);
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container">
      <h1>AI Alcohol Label Verifier</h1>
      <p className="subtitle">
        Upload label photos — each is OCR&apos;d, structured by Claude, and checked
        against a deterministic rule layer.
      </p>

      <UploadForm onSubmit={handleSubmit} loading={loading} />

      {error && <div className="error-banner">{error}</div>}

      {data && selected === null && (
        <ResultsGrid
          summary={data.summary}
          results={data.results}
          onSelect={setSelected}
        />
      )}

      {data && selected !== null && data.results[selected] && (
        <FindingsPanel
          result={data.results[selected]}
          onClose={() => setSelected(null)}
        />
      )}
    </main>
  );
}
