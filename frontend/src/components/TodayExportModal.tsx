import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { fmtDateDotted, todayISO } from "../lib/format";
import { groupBy } from "../lib/group-by";
import { bucketLabel } from "../lib/bucket-label";
import type { GanttItem } from "../types/api";
import { useToast } from "./Toast";

interface Props {
  items: GanttItem[];
  onClose: () => void;
}

/** Поля одной задачи в выгрузке — единая точка для text/html/JSX-рендеров ниже. */
interface ExportLine { key: string; url: string; summary: string; owner: string; bucket: string }

function isActiveToday(item: GanttItem, today: string): boolean {
  if (item.is_pseudo) return false;
  const startDay = item.start.slice(0, 10);
  const endDay = item.end.slice(0, 10);
  return startDay <= today && today <= endDay;
}

function groupByDirection(items: GanttItem[], noDirectionLabel: string): Record<string, GanttItem[]> {
  return groupBy(items, (it) => it.direction || noDirectionLabel);
}

function exportLine(it: GanttItem): ExportLine {
  return { key: it.key, url: it.url, summary: it.summary, owner: it.owner_file_name, bucket: it.bucket };
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function buildPlainText(items: GanttItem[], dateLabel: string, noDirectionLabel: string, t: (key: string) => string): string {
  const groups = groupByDirection(items, noDirectionLabel);
  const lines = [dateLabel];
  for (const [dir, list] of Object.entries(groups)) {
    lines.push("", `${dir}:`);
    for (const { key, summary, owner, bucket } of list.map(exportLine)) {
      lines.push(`- ${key} (${summary}) — ${owner} — ${bucketLabel(bucket, t)}`);
    }
  }
  return lines.join("\n");
}

function buildHtml(items: GanttItem[], dateLabel: string, noDirectionLabel: string, t: (key: string) => string): string {
  const groups = groupByDirection(items, noDirectionLabel);
  const parts = [`<div>${escapeHtml(dateLabel)}</div>`];
  for (const [dir, list] of Object.entries(groups)) {
    parts.push(`<div>&nbsp;</div><div><b>${escapeHtml(dir)}:</b></div>`);
    for (const { key, url, summary, owner, bucket } of list.map(exportLine)) {
      parts.push(
        `<div>- <a href="${escapeHtml(url)}">${escapeHtml(key)}</a> ` +
          `(${escapeHtml(summary)}) — ${escapeHtml(owner)} — ${escapeHtml(bucketLabel(bucket, t))}</div>`,
      );
    }
  }
  return parts.join("");
}

export function TodayExportModal({ items, onClose }: Props) {
  const { t } = useTranslation(["forecast", "common"]);
  const toast = useToast();
  const today = todayISO();

  const activeItems = useMemo(
    () => items.filter((it) => isActiveToday(it, today)),
    [items, today],
  );

  const noDirectionLabel = t("todayExport.noDirection");
  const dateLabel = t("todayExport.dateLabel", { date: fmtDateDotted(today) });
  const plainText = buildPlainText(activeItems, dateLabel, noDirectionLabel, t);
  const groups = groupByDirection(activeItems, noDirectionLabel);

  const handleCopy = async () => {
    try {
      if (typeof ClipboardItem !== "undefined" && navigator.clipboard.write) {
        const html = buildHtml(activeItems, dateLabel, noDirectionLabel, t);
        await navigator.clipboard.write([
          new ClipboardItem({
            "text/html": new Blob([html], { type: "text/html" }),
            "text/plain": new Blob([plainText], { type: "text/plain" }),
          }),
        ]);
      } else {
        await navigator.clipboard.writeText(plainText);
      }
      toast.success(t("todayExport.toast.copied"));
    } catch {
      try {
        await navigator.clipboard.writeText(plainText);
        toast.success(t("todayExport.toast.copied"));
      } catch {
        toast.error(t("todayExport.toast.copyFailed"));
      }
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="font-bold text-gray-900 text-lg">{t("todayExport.title")}</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {t("todayExport.summary", { date: fmtDateDotted(today), count: activeItems.length })}
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-4">
          {activeItems.length === 0 ? (
            <div className="text-center text-gray-400 py-10">
              {t("todayExport.empty")}
            </div>
          ) : (
            <div className="w-full border rounded-lg px-3 py-2 text-sm font-mono leading-relaxed bg-gray-50 space-y-2">
              <div>{dateLabel}</div>
              {Object.entries(groups).map(([dir, list]) => (
                <div key={dir}>
                  <div className="font-bold text-gray-900">{dir}:</div>
                  {list.map(exportLine).map(({ key, url, summary, owner, bucket }) => (
                    <div key={`${key}-${bucket}`}>
                      -{" "}
                      <a
                        href={url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-indigo-600 underline hover:text-indigo-800"
                      >
                        {key}
                      </a>{" "}
                      ({summary}) — {owner} — {bucketLabel(bucket, t)}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="border-t px-6 py-3 flex items-center justify-between bg-gray-50 rounded-b-2xl">
          <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700">
            {t("todayExport.close")}
          </button>
          <button
            onClick={handleCopy}
            disabled={activeItems.length === 0}
            className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-lg text-sm font-semibold"
          >
            {t("todayExport.copy")}
          </button>
        </div>
      </div>
    </div>
  );
}
