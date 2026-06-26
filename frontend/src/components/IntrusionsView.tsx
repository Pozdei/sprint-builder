import { useTranslation } from "react-i18next";
import type { IntrusionRecord } from "../types/intrusions";

interface Props {
  intrusions: IntrusionRecord[];
  terminalStatuses: string[];
}

/** Секция "Врывы" в раскрытом виде closed-спринта.
 *  Разбивка: сводка по (человек, роль), затем подробная таблица. */
export function IntrusionsView({ intrusions, terminalStatuses }: Props) {
  const { t } = useTranslation(["history", "common"]);
  if (intrusions.length === 0) {
    return (
      <div className="mt-4 text-sm text-gray-500 italic">
        {t("history:intrusions.empty")}
      </div>
    );
  }

  const terminalSet = new Set(terminalStatuses);

  // Сводка по (человек, роль)
  const byPersonRole = new Map<
    string,
    { fileName: string; role: string; count: number; hours: number;
      doneCount: number; doneHours: number }
  >();

  for (const it of intrusions) {
    const key = `${it.owner_file_name}|||${it.role}`;
    let rec = byPersonRole.get(key);
    if (!rec) {
      rec = {
        fileName: it.owner_file_name || "—",
        role: it.role,
        count: 0,
        hours: 0,
        doneCount: 0,
        doneHours: 0,
      };
      byPersonRole.set(key, rec);
    }
    rec.count += 1;
    rec.hours += it.hours;
    const done = it.is_done || terminalSet.has(it.status_name);
    if (done) {
      rec.doneCount += 1;
      rec.doneHours += it.hours;
    }
  }

  const totalHours = intrusions.reduce((s, it) => s + it.hours, 0);

  return (
    <div className="mt-6 border-t pt-4">
      <h3 className="font-semibold text-gray-700 mb-3">
        {t("history:intrusions.title", { count: intrusions.length, hours: totalHours.toFixed(1) })}
      </h3>

      <p className="text-xs text-gray-500 mb-3">
        {t("history:intrusions.description")}
      </p>

      {/* Сводка */}
      <div className="mb-4">
        <h4 className="text-sm font-semibold text-gray-600 mb-2">{t("history:intrusions.byPerson.title")}</h4>
        <table className="w-full text-sm border bg-white">
          <thead className="bg-gray-100">
            <tr>
              <th className="text-left px-3 py-1 border-b">{t("history:intrusions.byPerson.consultant")}</th>
              <th className="text-left px-3 py-1 border-b">{t("history:intrusions.byPerson.role")}</th>
              <th className="text-center px-3 py-1 border-b">{t("history:intrusions.byPerson.tasks")}</th>
              <th className="text-center px-3 py-1 border-b">{t("history:intrusions.byPerson.hours")}</th>
              <th className="text-center px-3 py-1 border-b">{t("history:intrusions.byPerson.done")}</th>
            </tr>
          </thead>
          <tbody>
            {Array.from(byPersonRole.values()).map((rec) => (
              <tr key={`${rec.fileName}-${rec.role}`} className="border-b">
                <td className="px-3 py-1">{rec.fileName}</td>
                <td className="px-3 py-1">{rec.role}</td>
                <td className="text-center px-3 py-1">{rec.count}</td>
                <td className="text-center px-3 py-1">{rec.hours.toFixed(1)}</td>
                <td className="text-center px-3 py-1">
                  {t("history:intrusions.byPerson.doneRatio", { done: rec.doneCount, total: rec.count, hours: rec.doneHours.toFixed(1) })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Подробно */}
      <h4 className="text-sm font-semibold text-gray-600 mb-2">{t("history:intrusions.list.title")}</h4>
      <div className="border rounded-lg overflow-hidden bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 border-b">
            <tr>
              <th className="text-left px-3 py-1.5 w-10"></th>
              <th className="text-left px-3 py-1.5 w-20">{t("history:intrusions.list.task")}</th>
              <th className="text-left px-3 py-1.5">{t("history:intrusions.list.name")}</th>
              <th className="text-left px-3 py-1.5">{t("history:intrusions.list.consultant")}</th>
              <th className="text-left px-3 py-1.5">{t("history:intrusions.list.role")}</th>
              <th className="text-left px-3 py-1.5">{t("history:intrusions.list.status")}</th>
              <th className="text-right px-3 py-1.5">{t("history:intrusions.list.hours")}</th>
            </tr>
          </thead>
          <tbody>
            {intrusions.map((it, i) => {
              const done = it.is_done || terminalSet.has(it.status_name);
              return (
                <tr
                  key={`${it.key}-${it.role}-${i}`}
                  className={`border-b ${done ? "bg-green-50" : "bg-yellow-50"}`}
                >
                  <td className="text-center px-3 py-1.5">
                    {done ? "✓" : "⏳"}
                  </td>
                  <td className="px-3 py-1.5 font-mono text-xs">
                    {it.url ? (
                      <a
                        href={it.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-blue-600 hover:underline"
                      >
                        {it.key}
                      </a>
                    ) : (
                      it.key
                    )}
                  </td>
                  <td className="px-3 py-1.5 max-w-[300px] truncate" title={it.summary}>
                    {it.summary}
                  </td>
                  <td className="px-3 py-1.5 text-gray-700">{it.owner_file_name}</td>
                  <td className="px-3 py-1.5 text-gray-700">{it.role}</td>
                  <td className="px-3 py-1.5 text-gray-600">{it.status_name}</td>
                  <td className="text-right px-3 py-1.5 font-semibold">
                    {it.hours.toFixed(1)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
