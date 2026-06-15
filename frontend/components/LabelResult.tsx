import type { ImageResult, LabelExtraction } from "../lib/types";

// Plain-language labels + how to render each extracted value, in reading order.
const FIELDS: { key: string; label: string; value: (f: LabelExtraction) => string }[] = [
  { key: "government_warning", label: "Government warning", value: (f) => (f.government_warning ? "Present" : "Not found") },
  { key: "abv", label: "Alcohol by volume (ABV)", value: (f) => (f.abv == null ? "—" : `${f.abv}%`) },
  { key: "brand_name", label: "Brand name", value: (f) => f.brand_name ?? "—" },
  { key: "class_type", label: "Class / type", value: (f) => f.class_type ?? "—" },
  { key: "net_contents", label: "Net contents", value: (f) => f.net_contents ?? "—" },
  { key: "producer", label: "Producer", value: (f) => f.producer ?? "—" },
];

export default function LabelResult({
  result,
  thumbnail,
}: {
  result: ImageResult;
  thumbnail?: string;
}) {
  const checks = result.field_validation;
  const rows = FIELDS.filter((f) => f.key in checks);
  const failedCount = rows.filter(({ key }) => !checks[key].passed).length;
  const overallPass = rows.length > 0 && failedCount === 0;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Overall status banner. */}
      <div className={`flex items-center gap-3 px-5 py-4 ${overallPass ? "bg-green-50" : "bg-red-50"}`}>
        {thumbnail && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={thumbnail}
            alt=""
            className="h-12 w-12 flex-none rounded-lg object-cover ring-1 ring-black/5"
          />
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-slate-500">{result.filename}</p>
          <p className={`text-lg font-bold ${overallPass ? "text-green-700" : "text-red-700"}`}>
            {overallPass
              ? "PASS — all checks passed"
              : `FAIL — ${failedCount} issue${failedCount === 1 ? "" : "s"} found`}
          </p>
        </div>
        <span
          aria-hidden
          className={`flex-none rounded-full px-3 py-1 text-sm font-extrabold ${
            overallPass ? "bg-green-600 text-white" : "bg-red-600 text-white"
          }`}
        >
          {overallPass ? "PASS" : "FAIL"}
        </span>
      </div>

      {/* Field-by-field checklist with the value Claude extracted. */}
      <ul className="divide-y divide-slate-100">
        {rows.map(({ key, label, value }) => {
          const { passed, reason } = checks[key];
          return (
            <li key={key} className="flex items-start gap-3 px-5 py-3">
              <span
                aria-hidden
                className={`mt-0.5 flex h-5 w-5 flex-none items-center justify-center rounded-full text-xs font-bold text-white ${
                  passed ? "bg-green-600" : "bg-red-600"
                }`}
              >
                {passed ? "✓" : "✗"}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-medium text-slate-800">{label}</span>
                  <span className="truncate text-sm text-slate-500" title={value(result.fields)}>
                    {value(result.fields)}
                  </span>
                </div>
                {!passed && reason && <p className="text-sm text-red-700">{reason}</p>}
              </div>
            </li>
          );
        })}
      </ul>

      {/* Soft warnings / notes (low OCR confidence, profile mismatches, etc.). */}
      {result.findings.length > 0 && (
        <div className="border-t border-slate-100 bg-amber-50/60 px-5 py-3">
          {result.findings.map((f, i) => (
            <p key={i} className="text-sm text-amber-800">
              {f.message}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
