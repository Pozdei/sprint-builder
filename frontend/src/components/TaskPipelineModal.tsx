import { useState } from "react";
import { useTranslation } from "react-i18next";
import { updateJiraIssueFields } from "../api/jira-client";
import { useToast } from "./Toast";
import { extractError } from "../lib/api-error";
import { BUCKET_TO_FIELD } from "../lib/bucket-fields";
import { bucketLabel } from "../lib/bucket-label";
import type { GanttItem } from "../types/api";

interface Props {
  taskKey: string;
  allItems: GanttItem[];   // все элементы Ганта (нужны для группировки по ключу)
  onClose: () => void;
  /** Вызывается после успешного сохранения часов в Jira — пересчитать прогноз
   * (расписание/позиции баров; сама цифра часов обновляется через onHoursSaved
   * сразу, без этого — пересчёт нужен только из-за возможного сдвига сроков). */
  onSaved?: () => void;
  /** Сразу применить новое значение часов к локальному состоянию прогноза —
   * не дожидаясь полного пересчёта (который ходит в Jira search/jql и может на
   * пару секунд отставать от только что записанного значения). */
  onHoursSaved?: (key: string, bucket: string, hours: number) => void;
}

const BUCKET_ORDER = [
  "Анализ", "Дизайн", "Разработка", "Код-ревью", "Дизайн-ревью", "Тестирование",
];

const BUCKET_COLORS: Record<string, { dot: string; bg: string; text: string }> = {
  "Анализ":       { dot: "bg-amber-400",   bg: "bg-amber-50",   text: "text-amber-800" },
  "Разработка":   { dot: "bg-green-500",   bg: "bg-green-50",   text: "text-green-800" },
  "Код-ревью":    { dot: "bg-emerald-500", bg: "bg-emerald-50", text: "text-emerald-800" },
  "Тестирование": { dot: "bg-blue-500",    bg: "bg-blue-50",    text: "text-blue-800" },
  "Дизайн":       { dot: "bg-pink-500",    bg: "bg-pink-50",    text: "text-pink-800" },
  "Дизайн-ревью": { dot: "bg-fuchsia-500", bg: "bg-fuchsia-50", text: "text-fuchsia-800" },
};
const DEFAULT_COLOR = { dot: "bg-gray-400", bg: "bg-gray-50", text: "text-gray-700" };

function fmtDT(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("ru-RU", {
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function bucketRank(bucket: string): number {
  const idx = BUCKET_ORDER.indexOf(bucket);
  return idx >= 0 ? idx : 99;
}

export function TaskPipelineModal({ taskKey, allItems, onClose, onSaved, onHoursSaved }: Props) {
  const { t } = useTranslation(["forecast", "common"]);
  const toast = useToast();
  // editValues[stageId] — введённое значение (строка); savingId — какой стейдж
  // сейчас сохраняется; savedIds — успешно сохранённые (показываем галочку вместо кнопки).
  const [editValues, setEditValues] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set());

  const handleSaveHours = async (stage: GanttItem, stageId: string) => {
    const field = BUCKET_TO_FIELD[stage.bucket];
    const raw = editValues[stageId];
    if (!field || raw === undefined) return;
    const n = parseFloat(raw);
    if (isNaN(n) || n <= 0) {
      toast.error(t("pipelineModal.toast.hoursMustBePositive"));
      return;
    }
    setSavingId(stageId);
    try {
      await updateJiraIssueFields(stage.key, { [field]: n });
      setSavedIds((prev) => new Set(prev).add(stageId));
      onHoursSaved?.(stage.key, stage.bucket, n);
      toast.success(t("pipelineModal.toast.hoursSaved", { key: stage.key, hours: n }));
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setSavingId(null);
    }
  };

  // Этапы задачи — либо по точному ключу, либо (для сводных баров Epic/User
  // Story/Консолидировано) все этапы всех задач группы по story_key/epic_key/parent_key.
  const stages = allItems
    .filter((it) => it.key === taskKey || it.story_key === taskKey || it.epic_key === taskKey || it.parent_key === taskKey)
    .sort((a, b) =>
      bucketRank(a.bucket) !== bucketRank(b.bucket)
        ? bucketRank(a.bucket) - bucketRank(b.bucket)
        : a.start_hours - b.start_hours,
    );

  if (stages.length === 0) return null;

  // Группа (Epic/Story/Консолидировано) — taskKey сам не встречается среди ключей задач.
  const isGroup = !stages.some((s) => s.key === taskKey);
  const first = stages[0];
  const last  = stages.reduce((a, b) => (a.end_hours > b.end_hours ? a : b));
  const totalHours = stages.reduce((s, it) => s + it.hours, 0);
  const direction = first.direction;

  const groupSummary = isGroup
    ? stages.find((s) => s.story_key === taskKey)?.story_summary
      ?? stages.find((s) => s.epic_key === taskKey)?.epic_summary
      ?? stages.find((s) => s.parent_key === taskKey)?.parent_summary
      ?? ""
    : first.summary;
  const groupUrl = isGroup && first.url
    ? first.url.replace(/\/browse\/[^/]+$/, `/browse/${taskKey}`)
    : first.url;

  // Дата завершения = конец последнего этапа
  const completionDate = new Date(last.end).toLocaleDateString("ru-RU", {
    day: "2-digit", month: "long", year: "numeric",
  });

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {groupUrl ? (
                <a
                  href={groupUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono font-bold text-blue-600 hover:underline text-base"
                >
                  {taskKey}
                </a>
              ) : (
                <span className="font-mono font-bold text-gray-800 text-base">{taskKey}</span>
              )}
              {!isGroup && direction && (
                <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-medium">
                  {direction}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-600 mt-0.5 leading-tight">
              {groupSummary}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none flex-none"
          >
            ×
          </button>
        </div>

        {/* Pipeline stages */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {/* Timeline line */}
          <div className="relative">
            {/* Vertical connector */}
            {stages.length > 1 && (
              <div
                className="absolute left-[11px] top-4 bottom-4 w-0.5 bg-gray-200"
                aria-hidden
              />
            )}

            <div className="space-y-3">
              {stages.map((stage, i) => {
                const col = BUCKET_COLORS[stage.bucket] ?? DEFAULT_COLOR;
                const isLast = i === stages.length - 1;
                const stageId = `${stage.key}|${stage.bucket}`;
                const field = BUCKET_TO_FIELD[stage.bucket];
                const editValue = editValues[stageId];
                const isDirty = editValue !== undefined && parseFloat(editValue) !== stage.hours;
                const isSaved = savedIds.has(stageId);
                return (
                  <div key={`${stage.key}-${stage.bucket}-${stage.start_hours}`} className="flex gap-3">
                    {/* Dot */}
                    <div className="flex-none flex flex-col items-center pt-1">
                      <div className={`w-5 h-5 rounded-full border-2 border-white shadow ${col.dot} z-10`} />
                    </div>

                    {/* Content */}
                    <div className={`flex-1 rounded-xl px-3 py-2.5 ${col.bg} ${isLast ? "ring-1 ring-inset ring-gray-200" : ""}`}>
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className={`text-sm font-semibold ${col.text}`}>
                          {bucketLabel(stage.bucket, t)}
                        </span>
                        {field ? (
                          <div className="flex items-center gap-1">
                            <input
                              type="number"
                              min={0.5}
                              step={0.5}
                              value={editValue ?? stage.hours}
                              onChange={(e) => setEditValues((p) => ({ ...p, [stageId]: e.target.value }))}
                              onWheel={(e) => e.currentTarget.blur()}
                              className="w-16 px-1.5 py-0.5 border rounded text-xs font-mono text-right bg-white/70 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                            />
                            <span className="text-xs text-gray-500">{t("pipelineModal.hoursUnit")}</span>
                            {isDirty && (
                              <button
                                onClick={() => handleSaveHours(stage, stageId)}
                                disabled={savingId === stageId}
                                title={t("pipelineModal.saveTitle")}
                                className="text-indigo-600 hover:text-indigo-800 font-bold text-sm disabled:opacity-40"
                              >
                                {savingId === stageId ? "…" : "✓"}
                              </button>
                            )}
                            {!isDirty && isSaved && (
                              <span className="text-green-600 text-xs" title={t("pipelineModal.savedTitle")}>✓</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs font-mono font-medium text-gray-600 bg-white/70 px-1.5 py-0.5 rounded">
                            {stage.hours.toFixed(1)} {t("pipelineModal.hoursUnit")}
                          </span>
                        )}
                      </div>
                      {isGroup && (
                        <div className="text-xs text-gray-500 mt-0.5 truncate">
                          {stage.url ? (
                            <a href={stage.url} target="_blank" rel="noreferrer" className="font-mono text-blue-600 hover:underline">
                              {stage.key}
                            </a>
                          ) : (
                            <span className="font-mono">{stage.key}</span>
                          )}
                          {" · "}{stage.summary}
                        </div>
                      )}
                      <div className="flex items-center justify-between mt-1 flex-wrap gap-x-3">
                        <span className="text-xs text-gray-600">
                          👤 {stage.owner_file_name}
                        </span>
                        <span className="text-xs text-gray-400 font-mono">
                          {fmtDT(stage.start)} → {fmtDT(stage.end)}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t px-5 py-3 bg-gray-50 rounded-b-2xl">
          {savedIds.size > 0 && onSaved && (
            <div className="flex items-center justify-between gap-3 mb-2.5 px-3 py-1.5 bg-green-50 border border-green-200 rounded-lg">
              <span className="text-xs text-green-800">
                {t("pipelineModal.footerNote")}
              </span>
              <button
                onClick={onSaved}
                className="text-xs font-semibold text-white bg-green-600 hover:bg-green-700 px-2.5 py-1 rounded-md flex-none"
              >
                {t("pipelineModal.recompute")}
              </button>
            </div>
          )}
          <div className="flex items-center justify-between">
            <div className="text-sm text-gray-500">
              <span className="font-medium text-gray-700">{t("pipelineModal.stagesCount", { count: stages.length })}</span> ·{" "}
              <span className="font-medium text-gray-700">{t("pipelineModal.totalHours", { hours: totalHours.toFixed(1) })}</span>
            </div>
            <div className="text-sm">
              <span className="text-gray-500">{t("pipelineModal.completion")} </span>
              <span className="font-semibold text-gray-800">{completionDate}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
