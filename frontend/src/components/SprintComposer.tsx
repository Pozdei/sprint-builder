import { useState } from "react";
import type { OwnerStat, TaskOut } from "../types/api";

interface Props {
  /** Все кандидаты (закэшированные при формировании). */
  candidates: TaskOut[];
  /** Текущий состав спринта. */
  sprintTasks: TaskOut[];
  /** Сводка по часам у людей. */
  ownerStats: OwnerStat[];
  /** Сохранить — вернётся обновлённый список спринта. */
  onSave: (newTasks: TaskOut[]) => Promise<void>;
  /** Сбросить — отменить изменения. */
  onCancel: () => void;
}

/**
 * Логика идентификации задачи: по комбинации key + role.
 * Псевдо-задачи имеют ключ "pseudo:..." — не редактируются (передвигать нельзя).
 */
function taskUid(t: TaskOut): string {
  return `${t.key}|${t.role}`;
}

export function SprintComposer({
  candidates, sprintTasks, ownerStats, onSave, onCancel,
}: Props) {
  // Локальные состояния (редактирование без сохранения)
  const [inSprint, setInSprint] = useState<TaskOut[]>(sprintTasks);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const inSprintUids = new Set(inSprint.map(taskUid));

  // Кандидаты, которые НЕ в спринте сейчас. Псевдо не показываем — они автоматические.
  const available = candidates.filter(
    (c) => !c.is_pseudo && !inSprintUids.has(taskUid(c)),
  );

  // Сортировка внутри спринта — по приоритету; псевдо первыми
  const sortedInSprint = [...inSprint].sort((a, b) => {
    if (a.is_pseudo !== b.is_pseudo) return a.is_pseudo ? -1 : 1;
    return (a.priority ?? 9999) - (b.priority ?? 9999);
  });

  // Сортировка кандидатов по приоритету
  const sortedAvailable = [...available].sort(
    (a, b) => (a.priority ?? 9999) - (b.priority ?? 9999),
  );

  // Пересчёт часов на лету
  const usedByOwner = new Map<string, number>();
  inSprint.forEach((t) => {
    usedByOwner.set(t.owner_id, (usedByOwner.get(t.owner_id) || 0) + t.hours);
  });

  const handleAdd = (t: TaskOut) => {
    setInSprint([...inSprint, t]);
  };

  const handleRemove = (t: TaskOut) => {
    if (t.is_pseudo) return;  // защита от удаления псевдо
    setInSprint(inSprint.filter((x) => taskUid(x) !== taskUid(t)));
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      await onSave(inSprint);
    } catch (e) {
      setError(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <div className="flex justify-between items-center mb-3">
        <h3 className="font-semibold text-gray-700">
          Редактирование состава спринта
        </h3>
        <div className="flex gap-2">
          <button
            onClick={onCancel}
            disabled={saving}
            className="bg-gray-300 hover:bg-gray-400 disabled:bg-gray-200 text-gray-800 px-3 py-1.5 rounded text-sm font-semibold"
          >
            Отмена
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white px-3 py-1.5 rounded text-sm font-semibold"
          >
            {saving ? "Сохраняю…" : "Сохранить состав"}
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-300 text-red-800 rounded p-2 mb-3 text-sm">
          {error}
        </div>
      )}

      {/* Сводка по людям с пересчётом на лету */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
        {ownerStats.map((s) => {
          const used = usedByOwner.get(s.owner_id) || 0;
          const over = used > s.budget;
          return (
            <div
              key={s.owner_id}
              className={`border rounded p-2 text-sm ${
                over ? "bg-red-50 border-red-300" : "bg-white"
              }`}
            >
              <div className="font-semibold text-gray-700">{s.file_name}</div>
              <div className={over ? "text-red-700 font-bold" : ""}>
                {used.toFixed(1)} / {s.budget} ч
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-4">
        {/* Левая колонка — кандидаты */}
        <div>
          <h4 className="font-semibold text-gray-600 text-sm mb-2">
            Кандидаты ({sortedAvailable.length})
          </h4>
          <TaskList
            tasks={sortedAvailable}
            actionLabel="→"
            actionTitle="Добавить в спринт"
            onAction={handleAdd}
            showPseudoButton={false}
          />
        </div>

        {/* Правая колонка — в спринте */}
        <div>
          <h4 className="font-semibold text-gray-600 text-sm mb-2">
            В спринте ({sortedInSprint.length})
          </h4>
          <TaskList
            tasks={sortedInSprint}
            actionLabel="←"
            actionTitle="Убрать из спринта"
            onAction={handleRemove}
            showPseudoButton={false}
          />
        </div>
      </div>
    </div>
  );
}

function TaskList({
  tasks, actionLabel, actionTitle, onAction, showPseudoButton,
}: {
  tasks: TaskOut[];
  actionLabel: string;
  actionTitle: string;
  onAction: (t: TaskOut) => void;
  showPseudoButton: boolean;
}) {
  if (tasks.length === 0) {
    return <div className="text-xs text-gray-400 italic px-2 py-4">пусто</div>;
  }
  return (
    <div className="border rounded bg-white max-h-[600px] overflow-y-auto">
      {tasks.map((t) => (
        <div
          key={taskUid(t)}
          className={`flex items-center gap-2 px-2 py-1.5 border-b text-sm hover:bg-gray-50 ${
            t.is_pseudo ? "bg-gray-50 italic text-gray-500" : ""
          }`}
        >
          <span className="text-gray-400 w-6">{t.priority ?? ""}</span>
          <span className="w-20 font-mono text-xs">
            {t.is_pseudo ? "(псевдо)" : t.key}
          </span>
          <span className="flex-1 truncate" title={t.summary}>
            {t.summary}
          </span>
          <span className="text-gray-500 text-xs w-20 truncate">
            {t.owner_file_name}
          </span>
          <span className="text-gray-700 text-xs font-semibold w-12 text-right">
            {t.hours.toFixed(1)}ч
          </span>
          {(!t.is_pseudo || showPseudoButton) ? (
            <button
              onClick={() => onAction(t)}
              className="text-blue-600 hover:text-blue-800 px-2 font-bold text-base"
              title={actionTitle}
            >
              {actionLabel}
            </button>
          ) : (
            <span className="w-7" />
          )}
        </div>
      ))}
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
