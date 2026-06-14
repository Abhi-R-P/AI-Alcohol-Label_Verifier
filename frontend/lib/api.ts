import type { ImageResult } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

async function toError(res: Response): Promise<Error> {
  let detail = `Request failed (${res.status})`;
  try {
    const body = await res.json();
    if (body?.detail) detail = body.detail;
  } catch {
    /* non-JSON error body */
  }
  return new Error(detail);
}

/**
 * Upload one or many label images and return a results array.
 * - 1 file  -> POST /upload-label (returns a single result)
 * - N files -> POST /verify       (returns { summary, results })
 */
export async function uploadLabels(files: File[]): Promise<ImageResult[]> {
  if (files.length === 1) {
    const form = new FormData();
    form.append("file", files[0]);
    const res = await fetch(`${API_BASE}/upload-label`, { method: "POST", body: form });
    if (!res.ok) throw await toError(res);
    return [await res.json()];
  }

  const form = new FormData();
  for (const file of files) form.append("files", file);
  const res = await fetch(`${API_BASE}/verify`, { method: "POST", body: form });
  if (!res.ok) throw await toError(res);
  const data = await res.json();
  return data.results;
}
