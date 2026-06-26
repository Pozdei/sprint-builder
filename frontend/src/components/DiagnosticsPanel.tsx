import { useState } from "react";
import { useTranslation } from "react-i18next";

interface SourceStat {
  source: string;
  kind: string;
  fetched?: number;
  matched?: number;
  skipped_epic?: number;
  error?: string;
}

interface Props {
  diagnostics: Record<string, unknown>;
}

export function DiagnosticsPanel({ diagnostics }: Props) {
  const { t } = useTranslation(["admin", "common"]);
  const [open, setOpen] = useState(false);

  const sources = (diagnostics.by_source ?? []) as SourceStat[];
  const errors = sources.filter((s) => s.error);
  const hasErrors = errors.length > 0;

  return (
    <div className="mb-3">
      <button
        onClick={() => setOpen((v) => !v)}
        className={`text-xs flex items-center gap-1.5 px-2 py-1 rounded border transition ${
          hasErrors
            ? "border-red-300 text-red-700 bg-red-50 hover:bg-red-100"
            : "border-gray-200 text-gray-500 bg-gray-50 hover:bg-gray-100"
        }`}
      >
        <span>{open ? "▾" : "▸"}</span>
        <span>{t("admin:diagnostics.toggleLabel")}</span>
        {hasErrors && (
          <span className="ml-1 bg-red-500 text-white text-xs px-1.5 py-0.5 rounded-full">
            {t("admin:diagnostics.errorsCount", { count: errors.length })}
          </span>
        )}
      </button>

      {open && (
        <div className="mt-2 border rounded-lg overflow-hidden text-xs">
          <table className="w-full">
            <thead className="bg-gray-100 text-gray-600">
              <tr>
                <th className="text-left px-3 py-1.5 font-semibold">{t("admin:diagnostics.table.source")}</th>
                <th className="text-left px-3 py-1.5 font-semibold">{t("admin:diagnostics.table.type")}</th>
                <th className="text-right px-3 py-1.5 font-semibold">{t("admin:diagnostics.table.fetched")}</th>
                <th className="text-right px-3 py-1.5 font-semibold">{t("admin:diagnostics.table.matched")}</th>
                <th className="text-right px-3 py-1.5 font-semibold">{t("admin:diagnostics.table.epics")}</th>
                <th className="text-left px-3 py-1.5 font-semibold">{t("admin:diagnostics.table.status")}</th>
              </tr>
            </thead>
            <tbody>
              {sources.map((s, i) => (
                <tr key={i} className={`border-t ${s.error ? "bg-red-50" : ""}`}>
                  <td className="px-3 py-1.5 font-mono">{s.source}</td>
                  <td className="px-3 py-1.5 text-gray-500">{s.kind}</td>
                  <td className="px-3 py-1.5 text-right">{s.fetched ?? "—"}</td>
                  <td className="px-3 py-1.5 text-right">{s.matched ?? "—"}</td>
                  <td className="px-3 py-1.5 text-right text-gray-400">
                    {s.skipped_epic ?? "—"}
                  </td>
                  <td className="px-3 py-1.5">
                    {s.error ? (
                      <span className="text-red-600" title={s.error}>
                        ✗ {s.error.slice(0, 60)}{s.error.length > 60 ? "…" : ""}
                      </span>
                    ) : (
                      <span className="text-green-600">✓</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
