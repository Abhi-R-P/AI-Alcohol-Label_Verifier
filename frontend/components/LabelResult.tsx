import type { FieldStatus, ImageResult, Verdict } from "../lib/types";

const FIELD_LABELS: Record<string, string> = {
  government_warning: "Government warning",
  brand_name: "Brand name",
  class_type: "Class / type",
  abv: "Alcohol by volume (ABV)",
  net_contents: "Net contents",
  bottler_name: "Bottler name",
  bottler_address: "Bottler address",
  country_of_origin: "Country of origin",
};
const FIELD_ORDER = Object.keys(FIELD_LABELS);

const STATUS_ICON: Record<FieldStatus, string> = { pass: "✓", warn: "!", fail: "✗", info: "–" };
const STATUS_DOT: Record<FieldStatus, string> = {
  pass: "bg-green-600",
  warn: "bg-amber-500",
  fail: "bg-red-600",
  info: "bg-slate-300",
};
const VERDICT_BANNER: Record<Verdict, string> = {
  PASS: "bg-green-50 text-green-800",
  WARN: "bg-amber-50 text-amber-800",
  FAIL: "bg-red-50 text-red-800",
};
const VERDICT_PILL: Record<Verdict, string> = {
  PASS: "bg-green-600",
  WARN: "bg-amber-500",
  FAIL: "bg-red-600",
};

export default function LabelResult({
  result,
  thumbnail,
}: {
  result: ImageResult;
  thumbnail?: string;
}) {
  const checks = result.field_validation;
  const rows = [
    ...FIELD_ORDER.filter((k) => k in checks),
    ...Object.keys(checks).filter((k) => !FIELD_ORDER.includes(k)),
  ];
  const counts = { pass: 0, warn: 0, fail: 0, info: 0 } as Record<FieldStatus, number>;
  for (const k of rows) counts[checks[k].status]++;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Overall status banner. */}
      <div className={`flex items-center gap-3 px-5 py-4 ${VERDICT_BANNER[result.verdict]}`}>
        {thumbnail && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={thumbnail} alt="" className="h-12 w-12 flex-none rounded-lg object-cover ring-1 ring-black/5" />
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-500">{result.filename}</p>
          <p className="text-lg font-bold">
            {result.verdict === "PASS" && "PASS — all checks passed"}
            {result.verdict === "WARN" && `WARN — ${counts.warn} to review`}
            {result.verdict === "FAIL" && `FAIL — ${counts.fail} issue${counts.fail === 1 ? "" : "s"}`}
          </p>
        </div>
        <span
          aria-hidden
          className={`flex-none rounded-full px-3 py-1 text-sm font-extrabold text-white ${VERDICT_PILL[result.verdict]}`}
        >
          {result.verdict}
        </span>
      </div>

      {/* Field-by-field checklist. */}
      <ul className="divide-y divide-slate-100">
        {rows.map((key) => {
          const r = checks[key];
          return (
            <li key={key} className="flex items-start gap-3 px-5 py-3">
              <span
                aria-hidden
                className={`mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full text-xs font-bold text-white ${STATUS_DOT[r.status]}`}
              >
                {STATUS_ICON[r.status]}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-medium text-slate-800">
                    {FIELD_LABELS[key] ?? key}
                  </span>
                  <span className="truncate text-sm text-slate-500" title={r.extracted ?? ""}>
                    {r.extracted ?? "—"}
                  </span>
                </div>
                {/* Show the expected value from the application, but not the long
                    mandated government-warning statement (noise). */}
                {r.expected && key !== "government_warning" && (
                  <p className="text-xs text-slate-400">Application: {r.expected}</p>
                )}
                {r.status !== "pass" && r.reason && (
                  <p
                    className={`text-sm ${
                      r.status === "fail"
                        ? "text-red-700"
                        : r.status === "warn"
                          ? "text-amber-700"
                          : "text-slate-400"
                    }`}
                  >
                    {r.reason}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ul>

      {/* Soft notes + processing time. */}
      {result.findings.length > 0 && (
        <div className="border-t border-slate-100 bg-amber-50/60 px-5 py-2">
          {result.findings.map((f, i) => (
            <p key={i} className="text-sm text-amber-800">{f.message}</p>
          ))}
        </div>
      )}
      <div className="border-t border-slate-100 px-5 py-2 text-xs text-slate-400">
        Processed in {(result.timings.total_ms / 1000).toFixed(1)}s · OCR confidence{" "}
        {result.ocr_confidence.toFixed(0)}
      </div>
    </div>
  );
}
