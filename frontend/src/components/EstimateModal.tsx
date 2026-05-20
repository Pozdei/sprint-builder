import { useState } from "react";
import { type IssueFieldsUpdate, updateJiraIssueFields } from "../api/jira-client";
import type { GanttItem } from "../types/api";

// Маппинг бакета → поле IssueFieldsUpdate
const BUCKET_TO_FIELD: Partial<Record<string, keyof IssueFieldsUpdate>> = {
  "Анализ":       "hours_analyst",
  "Разработка":   "hours_developer",
  "Тестирование": "hours_tester",
  "Дизайн":       "hours_designer",
};

const FIELD_LABEL: Record<string, string> = {
  hours_analyst:  "Аналитик",
  hours_developer:"Разработчик",
  hours_tester:   "Тестер",
  hours_designer: "Дизайнер",
};

const BUCKET_COLOR: Record<string, string> = {
  "Анализ":       "text-amber-700 bg-amber-50 border-amber-200",
  "Разработка":   "text-green-700 bg-green-50 border-green-200",
  "Тестирование": "text-blue-700 bg-blue-50 border-blue-200",
  "Дизайн":       "text-pink-700 bg-pink-50 border-pink-200",
};

interface MissingField {
  field: keyof IssueFieldsUpdate;
  bucket: string;
  defaultHours: number;
}

interface TaskRow {
  key: string;
  summary: string;
  url: string;
  missingFields: MissingField[];
}

interface SaveResult {
  key: string;
  ok: boolean;
  error?: string;
}

interface Props {
  items: GanttItem[];
  onClose: () => void;
  onSaved?: () => void;   // вызывается после успешного сохранения — можно пересчитать прогноз
}

function buildTaskRows(items: GanttItem[]): TaskRow[] {
  const byKey = new Map<string, TaskRow>();

  for (const item of items) {
    if (item.is_pseudo || !item.hours_is_default) continue;
    const field = BUCKET_TO_FIELD[item.bucket];
    if (!field) continue;  // ревью-бакеты — пропускаем

    if (!byKey.has(item.key)) {
      byKey.set(item.key, {
        key: item.key,
        summary: item.summary,
        url: item.url,
        missingFields: [],
      });
    }
    const row = byKey.get(item.key)!;
    // Не дублировать одно поле (один ключ может иметь несколько сегментов)
    if (!row.missingFields.some((f) => f.field === field)) {
      row.missingFields.push({ field, bucket: item.bucket, defaultHours: item.hours });
    }
  }

  return Array.from(byKey.values());
}

export function EstimateModal({ items, onClose, onSaved }: Props) {
  const tasks = buildTaskRows(items);

  // values[key][field] = введённое значение
  const [values, setValues] = useState<Record<string, Record<string, string>>>(() => {
    const init: Record<string, Record<string, string>> = {};
    for (const t of tasks) {
      init[t.key] = {};
      for (const f of t.missingFields) {
        init[t.key][f.field] = "";
      }
    }
    return init;
  });

  const [saving, setSaving] = useState(false);
  const [results, setResults] = useState<SaveResult[] | null>(null);

  const setValue = (key: string, field: string, val: string) => {
    setValues((prev) => ({
      ...prev,
      [key]: { ...prev[key], [field]: val },
    }));
  };

  // Считаем сколько заполнено
  const filledCount = tasks.reduce((n, t) =>
    n + t.missingFields.filter((f) => values[t.key]?.[f.field]?.trim()).length, 0);
  const totalFields = tasks.reduce((n, t) => n + t.missingFields.length, 0);

  const handleSave = async () => {
    setSaving(true);
    const res: SaveResult[] = [];

    for (const t of tasks) {
      const update: IssueFieldsUpdate = {};
      for (const f of t.missingFields) {
        const raw = values[t.key]?.[f.field]?.trim();
        if (!raw) continue;
        const n = parseFloat(raw);
        if (!isNaN(n) && n > 0) {
          (update as Record<string, number>)[f.field] = n;
        }
      }
      if (Object.keys(update).length === 0) continue;

      try {
        await updateJiraIssueFields(t.key, update);
        res.push({ key: t.key, ok: true });
      } catch (e: unknown) {
        const msg =
          e && typeof e === "object" && "response" in e
            ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? "Ошибка"
            : e instanceof Error ? e.message : "Ошибка";
        res.push({ key: t.key, ok: false, error: msg });
      }
    }

    setResults(res);
    setSaving(false);
    if (res.length > 0 && res.every((r) => r.ok) && onSaved) {
      onSaved();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b flex items-center justify-between">
          <div>
            <h2 className="font-bold text-gray-900 text-lg">Задачи без оценок</h2>
            <p className="text-sm text-gray-500 mt-0.5">
              {tasks.length} задач · {totalFields} полей не заполнены
            </p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
          {tasks.length === 0 && (
            <div className="text-center text-gray-400 py-10">
              Все задачи имеют оценки в Jira 🎉
            </div>
          )}

          {tasks.map((t) => (
            <div key={t.key} className="border rounded-xl overflow-hidden">
              {/* Task header */}
              <div className="px-4 py-2.5 bg-gray-50 border-b flex items-center gap-2">
                <a
                  href={t.url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono text-sm font-bold text-blue-600 hover:underline flex-none"
                >
                  {t.key}
                </a>
                <span className="text-sm text-gray-600 truncate">{t.summary}</span>
              </div>

              {/* Fields */}
              <div className="px-4 py-3 grid grid-cols-1 sm:grid-cols-2 gap-3">
                {t.missingFields.map((f) => (
                  <div key={f.field}>
                    <label className="flex items-center gap-2 text-xs font-medium text-gray-600 mb-1">
                      <span className={`px-2 py-0.5 rounded border text-xs ${BUCKET_COLOR[f.bucket] ?? "text-gray-600 bg-gray-50 border-gray-200"}`}>
                        {f.bucket}
                      </span>
                      {FIELD_LABEL[f.field]}
                      <span className="text-gray-400 font-normal">
                        (сейчас ~{f.defaultHours}ч дефолт)
                      </span>
                    </label>
                    <div className="flex items-center gap-1.5">
                      <input
                        type="number"
                        min={0.5}
                        step={0.5}
                        value={values[t.key]?.[f.field] ?? ""}
                        onChange={(e) => setValue(t.key, f.field, e.target.value)}
                        placeholder="часы"
                        className="w-24 px-2 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                      />
                      <span className="text-xs text-gray-400">ч</span>
                    </div>
                  </div>
                ))}
              </div>

              {/* Result badge */}
              {results && (() => {
                const r = results.find((r) => r.key === t.key);
                if (!r) return null;
                return (
                  <div className={`px-4 py-1.5 text-xs font-medium ${r.ok ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
                    {r.ok ? "✓ Сохранено в Jira" : `✗ ${r.error}`}
                  </div>
                );
              })()}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="border-t px-6 py-3 bg-gray-50 rounded-b-2xl flex items-center justify-between">
          <div className="text-sm text-gray-500">
            Заполнено: <span className="font-semibold text-gray-700">{filledCount}</span> из {totalFields}
          </div>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 border rounded-lg hover:bg-gray-100"
            >
              {results ? "Закрыть" : "Отмена"}
            </button>
            {!results && (
              <button
                onClick={handleSave}
                disabled={saving || filledCount === 0}
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white text-sm font-semibold rounded-lg"
              >
                {saving ? "Сохраняю…" : `Сохранить в Jira (${filledCount})`}
              </button>
            )}
            {results && onSaved && (
              <button
                onClick={() => { onSaved(); onClose(); }}
                className="px-5 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-semibold rounded-lg"
              >
                Пересчитать прогноз
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
