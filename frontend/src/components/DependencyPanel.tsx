import { useEffect, useState } from "react";
import type { GanttItem, TaskDependency } from "../types/api";

interface Props {
  ganttItems: GanttItem[];
  onFetchDeps: () => Promise<TaskDependency[]>;
  onAddDep: (dep: TaskDependency) => Promise<TaskDependency[]>;
  onRemoveDep: (dep: TaskDependency) => Promise<void>;
  onClose: () => void;
  onChanged: () => void;
}

export function DependencyPanel({
  ganttItems, onFetchDeps, onAddDep, onRemoveDep, onClose, onChanged,
}: Props) {
  const [deps, setDeps] = useState<TaskDependency[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [fromKey, setFromKey] = useState("");
  const [toKey, setToKey] = useState("");

  const taskKeys = Array.from(
    new Set(ganttItems.filter((i) => !i.is_pseudo).map((i) => i.key))
  ).sort();

  useEffect(() => {
    setLoading(true);
    onFetchDeps()
      .then(setDeps)
      .catch((e) => setError(extractError(e)))
      .finally(() => setLoading(false));
  }, []);

  const handleAdd = async () => {
    if (!fromKey || !toKey || fromKey === toKey) return;
    const dep: TaskDependency = { from_key: fromKey, to_key: toKey };
    setSaving(true);
    setError(null);
    try {
      const updated = await onAddDep(dep);
      setDeps(updated);
      setFromKey("");
      setToKey("");
      onChanged();
    } catch (e) {
      setError(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (dep: TaskDependency) => {
    setSaving(true);
    setError(null);
    try {
      await onRemoveDep(dep);
      setDeps((prev) => prev.filter((d) => !(d.from_key === dep.from_key && d.to_key === dep.to_key)));
      onChanged();
    } catch (e) {
      setError(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-80 bg-white border-l shadow-xl z-30 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50">
        <h2 className="text-sm font-semibold text-gray-800">Зависимости FS</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">×</button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {error && (
          <div className="bg-red-50 border border-red-300 text-red-800 rounded p-2 mb-3 text-xs">
            {error}
          </div>
        )}

        <div className="mb-4">
          <p className="text-xs text-gray-500 mb-2">
            Задача B стартует только после завершения всех этапов задачи A.
          </p>
          {loading ? (
            <div className="text-xs text-gray-400">Загрузка…</div>
          ) : deps.length === 0 ? (
            <div className="text-xs text-gray-400 italic">Нет зависимостей</div>
          ) : (
            <ul className="space-y-1.5">
              {deps.map((dep) => (
                <li
                  key={`${dep.from_key}→${dep.to_key}`}
                  className="flex items-center justify-between bg-gray-50 border rounded px-3 py-1.5"
                >
                  <span className="text-xs font-mono text-gray-700">
                    <span className="text-indigo-600 font-semibold">{dep.from_key}</span>
                    <span className="text-gray-400 mx-1">→</span>
                    <span className="text-green-700 font-semibold">{dep.to_key}</span>
                  </span>
                  <button
                    onClick={() => handleRemove(dep)}
                    disabled={saving}
                    className="text-red-400 hover:text-red-600 text-sm ml-2 disabled:opacity-40"
                    title="Удалить"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="border-t pt-4">
          <p className="text-xs font-semibold text-gray-600 mb-2">Добавить зависимость</p>
          <div className="space-y-2">
            <div>
              <label className="text-xs text-gray-500 block mb-0.5">Предшественник (A завершается раньше)</label>
              <select
                value={fromKey}
                onChange={(e) => setFromKey(e.target.value)}
                className="w-full border rounded px-2 py-1 text-xs"
              >
                <option value="">— выберите задачу —</option>
                {taskKeys.map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 block mb-0.5">Последователь (B стартует после)</label>
              <select
                value={toKey}
                onChange={(e) => setToKey(e.target.value)}
                className="w-full border rounded px-2 py-1 text-xs"
              >
                <option value="">— выберите задачу —</option>
                {taskKeys.filter((k) => k !== fromKey).map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            </div>
            <button
              onClick={handleAdd}
              disabled={!fromKey || !toKey || fromKey === toKey || saving}
              className="w-full bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white px-3 py-1.5 rounded text-xs font-semibold"
            >
              {saving ? "Сохраняю…" : "Добавить зависимость"}
            </button>
          </div>
        </div>
      </div>

      <div className="px-4 py-3 border-t bg-gray-50">
        <p className="text-xs text-gray-400">
          После изменений нажмите «Построить прогноз» для пересчёта.
        </p>
      </div>
    </div>
  );
}

function extractError(e: unknown): string {
  if (e && typeof e === "object" && "response" in e) {
    const r = (e as { response?: { data?: { detail?: string } } }).response;
    if (r?.data?.detail) return r.data.detail;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}
