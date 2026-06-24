import { useState } from "react";
import { fetchStandup, submitStandup } from "../api/client";
import { useToast } from "./Toast";
import { extractError } from "../lib/api-error";
import { fmtDateDotted, todayISO } from "../lib/format";
import type { RoleOut, SprintOut, StandupExecutor, StandupSubmitResult } from "../types/api";

const STATUSES = ["Выполнено", "В работе", "Заблокировано", "Не начинал"];

interface TaskState {
  status: string;
  comment: string;
  pushToJira: boolean;
}

interface Props {
  sprint: SprintOut;
  onClose: () => void;
}

function fmtTime(iso: string): string {
  return iso.slice(11, 16);
}

function bucketColor(bucket: string): string {
  const map: Record<string, string> = {
    "Анализ": "bg-amber-100 text-amber-800",
    "Разработка": "bg-green-100 text-green-800",
    "Код-ревью": "bg-emerald-100 text-emerald-800",
    "Тестирование": "bg-blue-100 text-blue-800",
    "Дизайн": "bg-pink-100 text-pink-800",
    "Дизайн-ревью": "bg-fuchsia-100 text-fuchsia-800",
  };
  return map[bucket] ?? "bg-gray-100 text-gray-700";
}

export function StandupModal({ sprint, onClose }: Props) {
  const toast = useToast();
  const roles: RoleOut[] = (sprint.config_snapshot.roles as RoleOut[] | undefined) ?? [];
  const enabledRoles = roles.filter((r) => r.enabled && !r.is_lead);
  const leadRoles   = roles.filter((r) => r.enabled && r.is_lead);
  const allEnabled  = [...enabledRoles, ...leadRoles];

  // --- Step 1: setup ---
  const approvedAt = sprint.approved_at
    ? sprint.approved_at.slice(0, 10)
    : todayISO();

  const [sprintStart, setSprintStart]   = useState(approvedAt);
  const [standupDate, setStandupDate]   = useState(todayISO());
  const [hoursPerDay, setHoursPerDay]   = useState(8);
  const [selectedRoles, setSelectedRoles] = useState<Set<string>>(
    new Set(allEnabled.map((r) => r.name)),
  );

  const [step, setStep] = useState<"setup" | "form" | "done">("setup");
  const [executors, setExecutors] = useState<StandupExecutor[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [results, setResults] = useState<StandupSubmitResult[]>([]);

  // task states keyed by "key|bucket"
  const [taskStates, setTaskStates] = useState<Record<string, TaskState>>({});

  const toggleRole = (name: string) => {
    setSelectedRoles((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  };

  const handleLoad = async () => {
    setLoading(true);
    try {
      const data = await fetchStandup(
        sprint.id,
        sprintStart,
        standupDate,
        hoursPerDay,
        Array.from(selectedRoles),
      );
      if (data.length === 0) {
        toast.info("По выбранным параметрам задач не найдено. Проверьте дату начала спринта и роли.");
        setLoading(false);
        return;
      }
      // Инициализируем начальные состояния задач
      const initial: Record<string, TaskState> = {};
      for (const ex of data) {
        for (const t of ex.tasks) {
          initial[`${t.key}|${t.bucket}`] = {
            status: t.is_overdue ? "Выполнено" : "В работе",
            comment: "",
            pushToJira: false,
          };
        }
      }
      setExecutors(data);
      setTaskStates(initial);
      setStep("form");
    } catch (e: unknown) {
      toast.error(extractError(e, "Ошибка загрузки"));
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    setSubmitting(true);

    const standupDateFmt = fmtDateDotted(standupDate);
    const updates: {
      key: string; owner_file_name: string; bucket: string;
      status: string; comment: string; push_to_jira: boolean;
    }[] = [];

    for (const ex of executors) {
      for (const t of ex.tasks) {
        const ts = taskStates[`${t.key}|${t.bucket}`];
        if (!ts) continue;
        updates.push({
          key: t.key,
          owner_file_name: ex.owner_file_name,
          bucket: t.bucket,
          status: ts.status,
          comment: ts.comment,
          push_to_jira: ts.pushToJira,
        });
      }
    }

    try {
      const res = await submitStandup({ standup_date: standupDateFmt, updates });
      setResults(res);
      setStep("done");
      const pushed = res.filter((r) => r.pushed).length;
      toast.success(
        pushed > 0
          ? `Стендап проведён · ${pushed} коммент. отправлено в Jira`
          : "Стендап проведён",
      );
    } catch (e: unknown) {
      toast.error(extractError(e, "Ошибка отправки"));
    } finally {
      setSubmitting(false);
    }
  };

  const pushCount = Object.values(taskStates).filter((ts) => ts.pushToJira).length;
  const totalTasks = Object.keys(taskStates).length;

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <div>
            <h2 className="font-bold text-gray-900 text-lg">
              Stand-up · Sprint {sprint.sprint_num}
            </h2>
            {step === "form" && (
              <p className="text-sm text-gray-500 mt-0.5">
                {fmtDateDotted(standupDate)} · {executors.length} участников · {totalTasks} задач
              </p>
            )}
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">×</button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">

          {/* ── Step 1: Setup ── */}
          {step === "setup" && (
            <div className="space-y-5">
              <div className="grid grid-cols-2 gap-4">
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">Дата стендапа</span>
                  <input
                    type="date"
                    value={standupDate}
                    onChange={(e) => setStandupDate(e.target.value)}
                    className="mt-1 w-full px-3 py-1.5 border rounded-lg text-sm"
                  />
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-gray-700">
                    Дата начала спринта
                    <span className="text-gray-400 font-normal ml-1">(для расчёта Ганта)</span>
                  </span>
                  <input
                    type="date"
                    value={sprintStart}
                    onChange={(e) => setSprintStart(e.target.value)}
                    className="mt-1 w-full px-3 py-1.5 border rounded-lg text-sm"
                  />
                </label>
              </div>

              <label className="block">
                <span className="text-sm font-medium text-gray-700">Рабочих часов в день</span>
                <input
                  type="number"
                  min={1} max={24} step={1}
                  value={hoursPerDay}
                  onChange={(e) => setHoursPerDay(Number(e.target.value))}
                  onWheel={(e) => e.currentTarget.blur()}
                  className="mt-1 w-24 px-3 py-1.5 border rounded-lg text-sm"
                />
              </label>

              <div>
                <span className="text-sm font-medium text-gray-700 block mb-2">
                  Роли участников стендапа
                </span>
                <div className="grid grid-cols-2 gap-y-2 gap-x-4">
                  {allEnabled.map((r) => (
                    <label key={r.name} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={selectedRoles.has(r.name)}
                        onChange={() => toggleRole(r.name)}
                        className="rounded"
                      />
                      <span className="text-sm text-gray-700">
                        {r.display_name}
                        {r.is_lead && <span className="text-gray-400 ml-1">(лид)</span>}
                      </span>
                    </label>
                  ))}
                </div>
                {allEnabled.length === 0 && (
                  <p className="text-sm text-gray-400 italic">Нет настроенных ролей в конфиге спринта.</p>
                )}
              </div>
            </div>
          )}

          {/* ── Step 2: Form ── */}
          {step === "form" && (
            <div className="space-y-6">
              {executors.map((ex) => (
                <div key={ex.owner_id} className="border rounded-xl overflow-hidden">
                  {/* Executor header */}
                  <div className="bg-gray-50 px-4 py-2 border-b flex items-center gap-2">
                    <span className="font-semibold text-gray-800">{ex.owner_file_name}</span>
                    <span className="text-xs text-gray-500 bg-gray-200 px-2 py-0.5 rounded-full">
                      {ex.role}
                    </span>
                    <span className="text-xs text-gray-400 ml-auto">
                      {ex.tasks.length} задач
                    </span>
                  </div>

                  {/* Tasks */}
                  <div className="divide-y">
                    {ex.tasks.map((t) => {
                      const tid = `${t.key}|${t.bucket}`;
                      const ts = taskStates[tid] ?? { status: "В работе", comment: "", pushToJira: false };

                      return (
                        <div key={tid} className="px-4 py-3 space-y-2">
                          {/* Task header */}
                          <div className="flex items-start gap-2 flex-wrap">
                            <a
                              href={t.url}
                              target="_blank"
                              rel="noreferrer"
                              className="font-mono text-sm font-semibold text-blue-600 hover:underline"
                            >
                              {t.key}
                            </a>
                            <span
                              className={`text-xs px-2 py-0.5 rounded-full font-medium ${bucketColor(t.bucket)}`}
                            >
                              {t.bucket}
                            </span>
                            {t.is_overdue && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-600 font-medium">
                                по плану завершена
                              </span>
                            )}
                            <span className="text-xs text-gray-400 ml-auto">
                              {fmtTime(t.planned_start)}→{fmtTime(t.planned_end)} · {t.planned_hours.toFixed(1)}ч
                            </span>
                          </div>
                          <p className="text-sm text-gray-600 leading-tight">{t.summary}</p>

                          {/* Controls */}
                          <div className="flex flex-wrap gap-3 items-start pt-1">
                            <div className="flex-none">
                              <label className="text-xs text-gray-500 block mb-0.5">Статус</label>
                              <select
                                value={ts.status}
                                onChange={(e) =>
                                  setTaskStates((prev) => ({
                                    ...prev,
                                    [tid]: { ...ts, status: e.target.value },
                                  }))
                                }
                                className="border rounded-lg px-2 py-1 text-sm bg-white min-w-[160px]"
                              >
                                {STATUSES.map((s) => (
                                  <option key={s} value={s}>{s}</option>
                                ))}
                              </select>
                            </div>

                            <div className="flex-1 min-w-[180px]">
                              <label className="text-xs text-gray-500 block mb-0.5">
                                Комментарий
                              </label>
                              <input
                                type="text"
                                value={ts.comment}
                                placeholder="Опционально…"
                                onChange={(e) =>
                                  setTaskStates((prev) => ({
                                    ...prev,
                                    [tid]: { ...ts, comment: e.target.value },
                                  }))
                                }
                                className="w-full border rounded-lg px-2 py-1 text-sm"
                              />
                            </div>

                            <div className="flex-none pt-5">
                              <label className="flex items-center gap-1.5 cursor-pointer text-sm text-gray-600">
                                <input
                                  type="checkbox"
                                  checked={ts.pushToJira}
                                  onChange={(e) =>
                                    setTaskStates((prev) => ({
                                      ...prev,
                                      [tid]: { ...ts, pushToJira: e.target.checked },
                                    }))
                                  }
                                />
                                Push to Jira
                              </label>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* ── Step 3: Done ── */}
          {step === "done" && (
            <div className="space-y-3">
              <p className="text-gray-700 font-medium">
                Стендап проведён · {fmtDateDotted(standupDate)}
              </p>
              {results.length > 0 && (
                <div className="border rounded-xl overflow-hidden">
                  {results.filter((r) => r.pushed || r.error).map((r, i) => (
                    <div key={i} className={`flex items-center gap-3 px-4 py-2 border-b last:border-b-0 ${r.error ? "bg-red-50" : "bg-green-50"}`}>
                      <span className="font-mono text-sm font-semibold text-blue-600">{r.key}</span>
                      <span className="text-xs text-gray-500">[{r.bucket}]</span>
                      {r.error
                        ? <span className="text-sm text-red-700 ml-auto">✗ {r.error}</span>
                        : <span className="text-sm text-green-700 ml-auto">✓ Комментарий добавлен в Jira</span>
                      }
                    </div>
                  ))}
                  {results.filter((r) => !r.pushed && !r.error).length > 0 && (
                    <div className="px-4 py-2 text-sm text-gray-500">
                      + {results.filter((r) => !r.pushed && !r.error).length} задач без отправки в Jira
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t px-6 py-3 flex items-center justify-between bg-gray-50 rounded-b-2xl">
          {step === "setup" && (
            <>
              <button onClick={onClose} className="text-sm text-gray-500 hover:text-gray-700">
                Отмена
              </button>
              <button
                onClick={handleLoad}
                disabled={loading || selectedRoles.size === 0}
                className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-lg text-sm font-semibold"
              >
                {loading ? "Загружаю…" : "Загрузить задачи →"}
              </button>
            </>
          )}

          {step === "form" && (
            <>
              <button
                onClick={() => setStep("setup")}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                ← Назад
              </button>
              <div className="flex items-center gap-3">
                {pushCount > 0 && (
                  <span className="text-xs text-gray-500">
                    {pushCount} из {totalTasks} задач → Jira
                  </span>
                )}
                <button
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-lg text-sm font-semibold"
                >
                  {submitting ? "Отправляю…" : "Провести стендап"}
                </button>
              </div>
            </>
          )}

          {step === "done" && (
            <button
              onClick={onClose}
              className="ml-auto bg-gray-800 hover:bg-gray-900 text-white px-5 py-2 rounded-lg text-sm font-semibold"
            >
              Закрыть
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
