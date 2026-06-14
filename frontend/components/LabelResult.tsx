import type { ImageResult } from "../lib/types";

// Plain-language labels and a friendly order for non-technical readers.
const FIELDS: { key: string; label: string }[] = [
  { key: "government_warning", label: "Government warning" },
  { key: "abv", label: "Alcohol by volume (ABV)" },
  { key: "brand_name", label: "Brand name" },
  { key: "class_type", label: "Class / type" },
  { key: "net_contents", label: "Net contents" },
  { key: "producer", label: "Producer" },
];

export default function LabelResult({ result }: { result: ImageResult }) {
  const checks = result.field_validation;
  // Order known fields first, then any extras the backend may add later.
  const ordered = [
    ...FIELDS.filter((f) => f.key in checks),
    ...Object.keys(checks)
      .filter((k) => !FIELDS.some((f) => f.key === k))
      .map((k) => ({ key: k, label: k })),
  ];
  const failedCount = ordered.filter(({ key }) => !checks[key].passed).length;
  const overallPass = ordered.length > 0 && failedCount === 0;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      {/* Overall status banner — the first thing a reader sees. */}
      <div
        className={`flex items-center justify-between px-5 py-4 ${
          overallPass ? "bg-green-50" : "bg-red-50"
        }`}
      >
        <div>
          <p className="truncate text-sm font-medium text-slate-500">{result.filename}</p>
          <p
            className={`text-lg font-bold ${
              overallPass ? "text-green-700" : "text-red-700"
            }`}
          >
            {overallPass
              ? "PASS — all checks passed"
              : `FAIL — ${failedCount} issue${failedCount === 1 ? "" : "s"} found`}
          </p>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-sm font-extrabold ${
            overallPass ? "bg-green-600 text-white" : "bg-red-600 text-white"
          }`}
        >
          {overallPass ? "PASS" : "FAIL"}
        </span>
      </div>

      {/* Field-by-field checklist. */}
      <ul className="divide-y divide-slate-100">
        {ordered.map(({ key, label }) => {
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
              <div className="min-w-0">
                <p className="font-medium text-slate-800">{label}</p>
                {passed ? (
                  <p className="text-sm text-green-700">Passed</p>
                ) : (
                  <p className="text-sm text-red-700">{reason ?? "Failed"}</p>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
