import type { Profile, VerifyResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export async function verifyImages(
  files: File[],
  profile?: Profile,
): Promise<VerifyResponse> {
  const form = new FormData();
  for (const file of files) {
    form.append("files", file);
  }
  if (profile && Object.keys(profile).length > 0) {
    form.append("profile", JSON.stringify(profile));
  }

  const res = await fetch(`${API_BASE}/verify`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = body.detail;
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }

  return res.json();
}
