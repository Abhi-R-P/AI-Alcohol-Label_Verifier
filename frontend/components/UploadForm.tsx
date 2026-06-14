"use client";

import { useState } from "react";
import type { Profile } from "../lib/types";

interface Props {
  onSubmit: (files: File[], profile: Profile) => void;
  loading: boolean;
}

export default function UploadForm({ onSubmit, loading }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [brand, setBrand] = useState("");
  const [abv, setAbv] = useState("");
  const [volume, setVolume] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (files.length === 0) return;

    const profile: Profile = {};
    if (brand.trim()) profile.brand_name = brand.trim();
    if (abv.trim() && !Number.isNaN(Number(abv))) profile.abv_percent = Number(abv);
    if (volume.trim()) profile.net_contents = volume.trim();

    onSubmit(files, profile);
  }

  return (
    <form className="card" onSubmit={handleSubmit}>
      <label htmlFor="files">Label images (JPEG / PNG / WebP — up to 10)</label>
      <input
        id="files"
        type="file"
        accept="image/png,image/jpeg,image/webp"
        multiple
        onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
      />

      <p className="meta" style={{ marginTop: "0.4rem" }}>
        {files.length > 0
          ? `${files.length} file${files.length > 1 ? "s" : ""} selected`
          : "No files selected"}
      </p>

      <details style={{ margin: "1rem 0" }}>
        <summary style={{ cursor: "pointer", color: "var(--muted)" }}>
          Optional: expected profile to validate against
        </summary>
        <div className="profile-grid" style={{ marginTop: "0.75rem" }}>
          <div>
            <label htmlFor="brand">Expected brand</label>
            <input
              id="brand"
              type="text"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              placeholder="Old Mill IPA"
            />
          </div>
          <div>
            <label htmlFor="abv">Expected ABV %</label>
            <input
              id="abv"
              type="number"
              step="0.1"
              value={abv}
              onChange={(e) => setAbv(e.target.value)}
              placeholder="6.5"
            />
          </div>
          <div>
            <label htmlFor="volume">Expected net contents</label>
            <input
              id="volume"
              type="text"
              value={volume}
              onChange={(e) => setVolume(e.target.value)}
              placeholder="355 mL"
            />
          </div>
        </div>
      </details>

      <button type="submit" disabled={loading || files.length === 0}>
        {loading ? "Verifying…" : "Verify labels"}
      </button>
    </form>
  );
}
