import { useEffect, useMemo, useState } from "react";
import { useToast } from "./Toast";
import { extractError } from "../lib/api-error";
import type { GanttItem, RootTaskOut, TaskDependency } from "../types/api";

interface Props {
  ganttItems: GanttItem[];
  onFetchDeps: () => Promise<TaskDependency[]>;
  onAddDep: (dep: TaskDependency) => Promise<TaskDependency[]>;
  onRemoveDep: (dep: TaskDependency) => Promise<void>;
  onFetchRootTasks?: () => Promise<RootTaskOut[]>;
  onSetRootTask?: (ownerId: string, taskKey: string) => Promise<RootTaskOut[]>;
  onRemoveRootTask?: (ownerId: string) => Promise<void>;
  onClose: () => void;
  onChanged: () => void;
}

export function DependencyPanel({
  ganttItems, onFetchDeps, onAddDep, onRemoveDep,
  onFetchRootTasks, onSetRootTask, onRemoveRootTask,
  onClose, onChanged,
}: Props) {
  const toast = useToast();
  const [deps, setDeps] = useState<TaskDependency[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [fromKey, setFromKey] = useState("");
  const [toKey, setToKey] = useState("");

  const [rootTasks, setRootTasks] = useState<RootTaskOut[]>([]);
  const [rootLoading, setRootLoading] = useState(true);
  const [rootSaving, setRootSaving] = useState(false);
  const [rootOwnerId, setRootOwnerId] = useState("");
  const [rootTaskKey, setRootTaskKey] = useState("");

  const taskKeys = useMemo(() => Array.from(
    new Set(ganttItems.filter((i) => !i.is_pseudo).map((i) => i.key))
  ).sort(), [ganttItems]);

  const owners = useMemo(() => Array.from(
    new Map(
      ganttItems
        .filter((i) => !i.is_pseudo)
        .map((i) => [i.owner_id, i.owner_file_name] as [string, string])
    ).entries()
  ).sort((a, b) => a[1].localeCompare(b[1])), [ganttItems]);

  const ownerTaskKeys = useMemo(() => Array.from(
    new Set(
      ganttItems
        .filter((i) => !i.is_pseudo && i.owner_id === rootOwnerId)
        .map((i) => i.key)
    )
  ).sort(), [ganttItems, rootOwnerId]);

  useEffect(() => {
    setLoading(true);
    onFetchDeps()
      .then(setDeps)
      .catch((e) => toast.error(extractError(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!onFetchRootTasks) {
      setRootLoading(false);
      return;
    }
    setRootLoading(true);
    onFetchRootTasks()
      .then(setRootTasks)
      .catch((e) => toast.error(extractError(e)))
      .finally(() => setRootLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAdd = async () => {
    if (!fromKey || !toKey || fromKey === toKey) return;
    const dep: TaskDependency = { from_key: fromKey, to_key: toKey };
    setSaving(true);
    try {
      const updated = await onAddDep(dep);
      setDeps(updated);
      setFromKey("");
      setToKey("");
      onChanged();
      toast.success(`Зависимость добавлена: ${dep.from_key} → ${dep.to_key}`);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (dep: TaskDependency) => {
    setSaving(true);
    try {
      await onRemoveDep(dep);
      setDeps((prev) => prev.filter((d) => !(d.from_key === dep.from_key && d.to_key === dep.to_key)));
      onChanged();
      toast.success("Зависимость удалена");
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  const handleSetRootTask = async () => {
    if (!onSetRootTask || !rootOwnerId || !rootTaskKey) return;
    setRootSaving(true);
    try {
      const updated = await onSetRootTask(rootOwnerId, rootTaskKey);
      setRootTasks(updated);
      setRootOwnerId("");
      setRootTaskKey("");
      onChanged();
      toast.success("Стартовая задача назначена");
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setRootSaving(false);
    }
  };

  const handleRemoveRootTask = async (ownerId: string) => {
    if (!onRemoveRootTask) return;
    setRootSaving(true);
    try {
      await onRemoveRootTask(ownerId);
      setRootTasks((prev) => prev.filter((r) => r.owner_id !== ownerId));
      onChanged();
      toast.success("Стартовая задача снята");
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setRootSaving(false);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-80 bg-white border-l shadow-xl z-30 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50">
        <h2 className="text-sm font-semibold text-gray-800">Зависимости FS</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">×</button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
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

        {onFetchRootTasks && (
          <div className="border-t pt-4 mt-4">
            <h3 className="text-sm font-semibold text-gray-800 mb-1">📌 Стартовые задачи</h3>
            <p className="text-xs text-gray-500 mb-2">
              Стартовая задача сотрудника встаёт первой в его очереди на Ганте — отражает,
              что он реально держит в работе прямо сейчас.
            </p>
            {rootLoading ? (
              <div className="text-xs text-gray-400">Загрузка…</div>
            ) : rootTasks.length === 0 ? (
              <div className="text-xs text-gray-400 italic mb-2">Не назначены</div>
            ) : (
              <ul className="space-y-1.5 mb-3">
                {rootTasks.map((rt) => {
                  const ownerName = owners.find(([id]) => id === rt.owner_id)?.[1] ?? rt.owner_id;
                  return (
                    <li
                      key={rt.owner_id}
                      className="flex items-center justify-between bg-amber-50 border border-amber-200 rounded px-3 py-1.5"
                    >
                      <span className="text-xs text-gray-700">
                        <span className="font-semibold">{ownerName}</span>
                        <span className="text-gray-400 mx-1">→</span>
                        <span className="font-mono text-amber-700 font-semibold">{rt.task_key}</span>
                      </span>
                      <button
                        onClick={() => handleRemoveRootTask(rt.owner_id)}
                        disabled={rootSaving}
                        className="text-red-400 hover:text-red-600 text-sm ml-2 disabled:opacity-40"
                        title="Снять"
                      >
                        ×
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}

            <div className="space-y-2">
              <div>
                <label className="text-xs text-gray-500 block mb-0.5">Сотрудник</label>
                <select
                  value={rootOwnerId}
                  onChange={(e) => { setRootOwnerId(e.target.value); setRootTaskKey(""); }}
                  className="w-full border rounded px-2 py-1 text-xs"
                >
                  <option value="">— выберите сотрудника —</option>
                  {owners.map(([id, name]) => (
                    <option key={id} value={id}>{name}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-500 block mb-0.5">Стартовая задача</label>
                <select
                  value={rootTaskKey}
                  onChange={(e) => setRootTaskKey(e.target.value)}
                  disabled={!rootOwnerId}
                  className="w-full border rounded px-2 py-1 text-xs disabled:bg-gray-100"
                >
                  <option value="">— выберите задачу —</option>
                  {ownerTaskKeys.map((k) => (
                    <option key={k} value={k}>{k}</option>
                  ))}
                </select>
              </div>
              <button
                onClick={handleSetRootTask}
                disabled={!rootOwnerId || !rootTaskKey || rootSaving}
                className="w-full bg-amber-600 hover:bg-amber-700 disabled:bg-gray-300 text-white px-3 py-1.5 rounded text-xs font-semibold"
              >
                {rootSaving ? "Сохраняю…" : "Назначить стартовой"}
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="px-4 py-3 border-t bg-gray-50">
        <p className="text-xs text-gray-400">
          После изменений нажмите «Построить прогноз» для пересчёта.
        </p>
      </div>
    </div>
  );
}