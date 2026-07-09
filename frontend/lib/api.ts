import type { ApplicationData, ImageResult } from "./types";

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

function hasValues(app?: ApplicationData): boolean {
  return !!app && Object.values(app).some((v) => v !== undefined && v !== "" && v !== null);
}

/**
 * Upload one or many label images and return a results array.
 * - 1 file  -> POST /upload-label
 * - N files -> POST /verify (optional CSV of per-image expected values)
 * `application` supplies expected COLA values (applied to all images).
 */
export async function uploadLabels(
  files: File[],
  application?: ApplicationData,
  csvFile?: File | null,
): Promise<ImageResult[]> {
  const appJson = hasValues(application) ? JSON.stringify(application) : null;

  if (files.length === 1 && !csvFile) {
    const form = new FormData();
    form.append("file", files[0]);
    if (appJson) form.append("application", appJson);
    const res = await fetch(`${API_BASE}/upload-label`, { method: "POST", body: form });
    if (!res.ok) throw await toError(res);
    return [await res.json()];
  }

  const form = new FormData();
  for (const file of files) form.append("files", file);
  if (appJson) form.append("application", appJson);
  if (csvFile) form.append("csv_file", csvFile);
  const res = await fetch(`${API_BASE}/verify`, { method: "POST", body: form });
  if (!res.ok) throw await toError(res);
  const data = await res.json();
  return data.results;
}
