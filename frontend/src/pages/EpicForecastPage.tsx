import { useState } from "react";
import {
  addEpicDependency, fetchEpicDependencies,
  fetchEpicForecast, fetchEpicSnapshots, removeEpicDependency,
} from "../api/client";
import { DependencyPanel } from "../components/DependencyPanel";
import { EstimateModal } from "../components/EstimateModal";
import { ForecastTrendChart } from "../components/ForecastTrendChart";
import { GanttChart } from "../components/GanttChart";
import { TaskPipelineModal } from "../components/TaskPipelineModal";
import { useToast } from "../components/Toast";
import { VacationPanel } from "../components/VacationPanel";
import { extractError } from "../lib/api-error";
import { triggerDownload } from "../lib/download";
import { daysUntil, fmtDateLong, fmtNum, fmtRub, todayISO } from "../lib/format";
import { loadRecentEpics, pushRecentEpic, removeRecentEpic } from "../lib/recent-epics";
import type { CostBreakdownItem, EpicForecastResponse, EpicForecastSnapshot, TaskDependency } from "../types/api";

export function EpicForecastPage({ isAdmin = false }: { isAdmin?: boolean }) {
  const toast = useToast();
  const [epicKey,    setEpicKey]    = useState("");
  const [startDate,  setStartDate]  = useState(todayISO());
  const [hoursPerDay, setHoursPerDay] = useState(8);

  const [loading,  setLoading]  = useState(false);
  const [result,   setResult]   = useState<EpicForecastResponse | null>(null);
  const [selectedKey,    setSelectedKey]    = useState<string | null>(null);
  const [showEstimates,  setShowEstimates]  = useState(false);

  const [showCostBreakdown, setShowCostBreakdown] = useState(false);
  const [showRoi,       setShowRoi]       = useState(false);
  const [showDeps,      setShowDeps]      = useState(false);
  const [showVacations, setShowVacations] = useState(false);
  const [epicDeps,      setEpicDeps]      = useState<TaskDependency[]>([]);
  const [snapshots,     setSnapshots]     = useState<EpicForecastSnapshot[]>([]);
  const [useHistory,    setUseHistory]    = useState(false);
  const [recentEpics,   setRecentEpics]   = useState<string[]>(() => loadRecentEpics());

  // overrideKey — если передан (клик по чипсу), считаем сразу по нему, не дожидаясь setState.
  const handleForecast = async (overrideKey?: string) => {
    const key = (overrideKey ?? epicKey).trim().toUpperCase();
    if (!key) return;
    if (overrideKey) setEpicKey(key);
    setLoading(true);
    setResult(null);
    try {
      const [data, deps] = await Promise.all([
        fetchEpicForecast(key, startDate, hoursPerDay, useHistory),
        fetchEpicDependencies(key),
      ]);
      setResult(data);
      setEpicDeps(deps);
      // Снапшоты загружаем после forecast (бэкенд уже сохранил новый)
      fetchEpicSnapshots(key).then(setSnapshots).catch(() => {});
      setRecentEpics(pushRecentEpic(key));
      toast.success(
        data.completion_date
          ? `${data.epic_key}: прогноз построен — ${fmtDateLong(data.completion_date)}`
          : `${data.epic_key}: прогноз построен`,
      );
    } catch (e: unknown) {
      toast.error(extractError(e));
    } finally {
      setLoading(false);
    }
  };

  const days = result?.completion_date ? daysUntil(result.completion_date) : null;

  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
      <div className="mb-6">
        <h1 className="text-xl font-bold text-gray-800 mb-1">Прогноз реализации</h1>
        <p className="text-sm text-gray-500">
          Введите ключ эпика или задачи — система рассчитает расписание
          оставшихся этапов и предскажет дату завершения.
        </p>
      </div>

      {/* Форма ввода */}
      <div className="bg-white rounded-xl border shadow-sm p-5 mb-6">
        <div className="flex flex-wrap gap-4 items-end">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Ключ эпика</label>
            <input
              type="text"
              value={epicKey}
              onChange={(e) => setEpicKey(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleForecast()}
              placeholder="SHN-1947 или SHN-2353"
              className="px-3 py-2 border rounded-lg text-sm font-mono w-40 focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Старт расчёта</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="px-3 py-2 border rounded-lg text-sm"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Ч/день</label>
            <input
              type="number"
              min={1} max={24} step={1}
              value={hoursPerDay}
              onChange={(e) => setHoursPerDay(Number(e.target.value))}
              className="px-3 py-2 border rounded-lg text-sm w-20"
            />
          </div>
          <button
            onClick={() => handleForecast()}
            disabled={loading || !epicKey.trim()}
            className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300
                       text-white font-semibold px-5 py-2 rounded-lg text-sm transition"
          >
            {loading ? "Считаю…" : "Построить прогноз"}
          </button>
          <label
            className="flex items-center gap-2 cursor-pointer select-none ml-1"
            title="Восстановить прошлые фазы по истории Jira (кто и когда был на аналитике/разработке/тесте) и показать их на одной шкале с прогнозом"
            onClick={() => setUseHistory(v => !v)}
          >
            <div className={`relative w-9 h-5 rounded-full transition-colors ${useHistory ? "bg-indigo-500" : "bg-gray-300"}`}>
              <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${useHistory ? "translate-x-4" : "translate-x-0.5"}`} />
            </div>
            <span className="text-sm text-gray-600">По истории статусов</span>
          </label>
        </div>

        {recentEpics.length > 0 && (
          <div className="mt-3 flex items-center gap-2 flex-wrap">
            <span className="text-xs text-gray-400">Недавние:</span>
            {recentEpics.map((k) => (
              <span
                key={k}
                className="group inline-flex items-center gap-1 bg-gray-100 hover:bg-indigo-50
                           border border-transparent hover:border-indigo-200 rounded-full
                           pl-2.5 pr-1 py-0.5 text-xs font-mono text-gray-600 transition"
              >
                <button
                  onClick={() => handleForecast(k)}
                  disabled={loading}
                  className="hover:text-indigo-700 disabled:opacity-50"
                  title={`Построить прогноз для ${k}`}
                >
                  {k}
                </button>
                <button
                  onClick={() => setRecentEpics(removeRecentEpic(k))}
                  className="text-gray-300 hover:text-red-500 leading-none px-0.5"
                  title="Убрать из недавних"
                >
                  ×
                </button>
              </span>
            ))}
          </div>
        )}
      </div>

      {loading && !result && <ForecastSkeleton />}

      {result && (
        <>
          {/* Заголовок с предиктом */}
          <div className="mb-5 flex flex-wrap gap-4 items-start">
            {/* Главная карточка: дата завершения */}
            <div className={`flex-none rounded-2xl p-5 shadow-sm border-2 ${
              days === null ? "border-gray-200 bg-gray-50" :
              days < 0    ? "border-red-300 bg-red-50" :
              days <= 14  ? "border-amber-300 bg-amber-50" :
                            "border-indigo-300 bg-indigo-50"
            }`}>
              <div className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">
                Прогноз завершения
              </div>
              {result.completion_date ? (
                <>
                  <div className={`text-2xl font-bold ${
                    days === null ? "text-gray-700" :
                    days < 0     ? "text-red-700" :
                    days <= 14   ? "text-amber-700" :
                                   "text-indigo-700"
                  }`}>
                    {fmtDateLong(result.completion_date)}
                  </div>
                  {days !== null && (
                    <div className="text-sm mt-0.5 text-gray-500">
                      {days < 0  ? `просрочено на ${Math.abs(days)} дн.` :
                       days === 0 ? "сегодня" :
                                    `через ${days} дн.`}
                    </div>
                  )}
                </>
              ) : (
                <div className="text-lg text-gray-400 italic">нет данных</div>
              )}
            </div>

            {/* Сводка */}
            <div className="flex-1 bg-white rounded-2xl border shadow-sm p-5">
              <div className="text-sm font-semibold text-gray-700 mb-3">
                {result.epic_key} · {result.epic_summary}
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: "Всего задач",     value: result.stats.total_issues,
                    icon: METRIC_ICONS.total, accent: "text-slate-500 bg-slate-100" },
                  { label: "Выполнено",        value: result.stats.done_issues,
                    icon: METRIC_ICONS.done, accent: "text-green-600 bg-green-100",
                    sub: `${Math.round(result.stats.done_issues / Math.max(result.stats.total_issues,1)*100)}%` },
                  { label: "Осталось задач",  value: result.stats.total_issues - result.stats.done_issues,
                    icon: METRIC_ICONS.remaining, accent: "text-indigo-600 bg-indigo-100",
                    sub: `${result.stats.remaining_work_items} эт. в расписании` },
                  { label: "Плановых часов",  value: `${result.stats.total_planned_hours} ч`,
                    warn: result.stats.default_hours_count > 0,
                    icon: METRIC_ICONS.hours,
                    accent: result.stats.default_hours_count > 0
                      ? "text-amber-600 bg-amber-100" : "text-blue-600 bg-blue-100",
                    sub: result.stats.default_hours_count > 0
                      ? `${result.stats.default_hours_count} без оценки`
                      : "все оценены" },
                ].map((m) => (
                  <div
                    key={m.label}
                    className="bg-gray-50 rounded-xl px-3 py-2.5 border border-transparent
                               hover:border-gray-200 hover:bg-white hover:shadow-sm transition"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`w-6 h-6 rounded-lg flex items-center justify-center ${m.accent}`}>
                        {m.icon}
                      </span>
                      <div className="text-xs text-gray-500">{m.label}</div>
                    </div>
                    <div className={`text-xl font-bold leading-none ${m.warn ? "text-amber-600" : "text-gray-800"}`}>
                      {m.value}
                    </div>
                    {m.sub && (
                      <div className={`text-xs mt-1 ${m.warn ? "text-amber-500" : "text-gray-400"}`}>
                        {m.sub}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {result.stats.total_cost > 0 && (
                <div className="mt-3 bg-blue-50 rounded-xl px-4 py-2.5 flex items-center gap-3 flex-wrap">
                  <span className="text-xs text-blue-500">Стоимость проекта</span>
                  <span className="text-2xl font-bold text-blue-700">
                    {fmtRub(result.stats.total_cost)}
                  </span>
                  <span className="text-xs text-blue-400">по окладам команды</span>
                  <div className="ml-auto flex items-center gap-3">
                    <button
                      onClick={() => setShowRoi(true)}
                      className="text-xs font-semibold text-white bg-blue-600 hover:bg-blue-700 rounded-lg px-3 py-1.5 transition"
                    >
                      Посчитать ROI
                    </button>
                    {isAdmin && (
                      <button
                        onClick={() => setShowCostBreakdown(true)}
                        className="text-xs text-blue-600 hover:text-blue-800 underline underline-offset-2"
                      >
                        Подробный расчёт
                      </button>
                    )}
                  </div>
                </div>
              )}
              {result.today_hours != null && (
                <div className="mt-2 flex items-center gap-3 flex-wrap text-sm">
                  <span className="inline-flex items-center gap-2 bg-gray-100 rounded-lg px-3 py-1.5">
                    <span className="text-xs text-gray-500">Потрачено</span>
                    <span className="font-semibold text-gray-700">{fmtRub(result.stats.spent_cost ?? 0)}</span>
                    <span className="text-xs text-gray-400">· {fmtNum(result.stats.spent_hours ?? 0, 1)} ч</span>
                  </span>
                  <span className="inline-flex items-center gap-2 bg-indigo-50 rounded-lg px-3 py-1.5">
                    <span className="text-xs text-indigo-500">Осталось</span>
                    <span className="font-semibold text-indigo-700">{fmtRub(result.stats.remaining_cost ?? 0)}</span>
                    <span className="text-xs text-indigo-400">· {fmtNum(result.stats.remaining_hours ?? 0, 1)} ч</span>
                  </span>
                  <span className="text-xs text-gray-400">
                    левее красной линии на диаграмме — факт по истории Jira
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Предупреждения */}
          {result.warnings.length > 0 && (
            <div className="mb-4 bg-amber-50 border border-amber-200 rounded-xl p-4">
              <div className="font-semibold text-amber-800 text-sm mb-1">
                ⚠ Задачи с неизвестным статусом ({result.warnings.length}) — расписаны с начала pipeline
              </div>
              <div className="text-xs text-amber-700 space-y-0.5">
                {result.warnings.slice(0, 8).map((w, i) => <div key={i}>{w}</div>)}
                {result.warnings.length > 8 && (
                  <div>…и ещё {result.warnings.length - 8}</div>
                )}
              </div>
            </div>
          )}

          {/* Гант */}
          {result.gantt_items.length > 0 ? (
            <>
              {/* Шапка с кнопками */}
              <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
                <p className="text-xs text-gray-400">
                  Клик — все этапы · двойной — Jira
                </p>
                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    onClick={() => { setShowDeps((v) => !v); setShowVacations(false); }}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition ${
                      showDeps
                        ? "bg-red-50 border-red-300 text-red-700"
                        : "border-gray-300 text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    Зависимости{epicDeps.length > 0 ? ` (${epicDeps.length})` : ""}
                  </button>
                  <button
                    onClick={() => { setShowVacations((v) => !v); setShowDeps(false); }}
                    className={`px-3 py-1.5 rounded-lg text-sm font-medium border transition ${
                      showVacations
                        ? "bg-orange-50 border-orange-300 text-orange-700"
                        : "border-gray-300 text-gray-600 hover:bg-gray-50"
                    }`}
                  >
                    Отпуска
                  </button>
                  {result.stats.default_hours_count > 0 && (
                    <button
                      onClick={() => setShowEstimates(true)}
                      className="flex items-center gap-1.5 text-sm font-medium px-3 py-1.5
                                 bg-amber-50 border border-amber-300 text-amber-700
                                 hover:bg-amber-100 rounded-lg transition"
                    >
                      <span className="w-5 h-5 bg-amber-400 text-white rounded-full text-xs flex items-center justify-center font-bold">
                        {result.stats.default_hours_count}
                      </span>
                      Без оценок
                    </button>
                  )}
                </div>
              </div>
              <GanttChart
                items={result.gantt_items}
                startDate={result.gantt_start ?? startDate}
                hoursPerDay={hoursPerDay}
                dependencies={epicDeps}
                onTaskClick={setSelectedKey}
                todayHours={result.today_hours}
              />
            </>
          ) : (
            <div className="text-center text-gray-400 py-10">
              Все задачи эпика выполнены или нет задач с известными исполнителями.
            </div>
          )}

          {selectedKey && result && (
            <TaskPipelineModal
              taskKey={selectedKey}
              allItems={result.gantt_items}
              onClose={() => setSelectedKey(null)}
            />
          )}

          <ForecastTrendChart
            snapshots={snapshots}
            onDeleted={(id) => setSnapshots((prev) => prev.filter((s) => s.id !== id))}
            onPinToggled={(updated) =>
              setSnapshots((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
            }
          />

          {showEstimates && result && (
            <EstimateModal
              items={result.gantt_items}
              onClose={() => setShowEstimates(false)}
              onSaved={() => {
                setShowEstimates(false);
                handleForecast();
              }}
            />
          )}

          {showDeps && result && (
            <DependencyPanel
              ganttItems={result.gantt_items}
              onFetchDeps={() => fetchEpicDependencies(epicKey.trim().toUpperCase())}
              onAddDep={(dep) => addEpicDependency(epicKey.trim().toUpperCase(), dep)}
              onRemoveDep={(dep) => removeEpicDependency(epicKey.trim().toUpperCase(), dep)}
              onClose={() => setShowDeps(false)}
              onChanged={() => {
                fetchEpicDependencies(epicKey.trim().toUpperCase()).then(setEpicDeps);
                handleForecast();
              }}
            />
          )}

          {showVacations && result && (
            <VacationPanel
              ganttItems={result.gantt_items}
              onClose={() => setShowVacations(false)}
              onChanged={handleForecast}
            />
          )}

          {showCostBreakdown && result && (
            <CostBreakdownModal
              breakdown={result.cost_breakdown ?? []}
              totalCost={result.stats.total_cost}
              onClose={() => setShowCostBreakdown(false)}
            />
          )}

          {showRoi && result && (
            <RoiModal
              totalCost={result.stats.total_cost}
              onClose={() => setShowRoi(false)}
            />
          )}
        </>
      )}
    </div>
  );
}

/** Иконки для метрик-карточек сводки (20×20 inline SVG). */
const METRIC_ICONS = {
  total: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
      <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zm0 5a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V9zm0 5a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1v-2z" />
    </svg>
  ),
  done: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
      <path fillRule="evenodd" d="M16.7 5.3a1 1 0 010 1.4l-7.5 7.5a1 1 0 01-1.4 0L3.3 9.7a1 1 0 011.4-1.4l3.1 3.1 6.8-6.8a1 1 0 011.4 0z" clipRule="evenodd" />
    </svg>
  ),
  remaining: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM11 6a1 1 0 10-2 0v4a1 1 0 00.3.7l2.5 2.5a1 1 0 001.4-1.4L11 9.6V6z" clipRule="evenodd" />
    </svg>
  ),
  hours: (
    <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
      <path fillRule="evenodd" d="M10 2a1 1 0 011 1v6.4l4 2.3a1 1 0 01-1 1.7l-4.5-2.6A1 1 0 019 10V3a1 1 0 011-1z" clipRule="evenodd" />
    </svg>
  ),
};

/** Скелетон-заглушка на время расчёта прогноза. */
function ForecastSkeleton() {
  return (
    <div className="mb-5 flex flex-wrap gap-4 items-start animate-pulse">
      <div className="flex-none rounded-2xl p-5 border-2 border-gray-100 bg-gray-50 w-56">
        <div className="h-3 w-28 bg-gray-200 rounded mb-3" />
        <div className="h-7 w-40 bg-gray-200 rounded mb-2" />
        <div className="h-3 w-20 bg-gray-200 rounded" />
      </div>
      <div className="flex-1 bg-white rounded-2xl border shadow-sm p-5 min-w-[280px]">
        <div className="h-4 w-48 bg-gray-200 rounded mb-4" />
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="bg-gray-50 rounded-xl px-3 py-2.5">
              <div className="h-6 w-6 bg-gray-200 rounded-lg mb-2" />
              <div className="h-5 w-12 bg-gray-200 rounded mb-1.5" />
              <div className="h-3 w-16 bg-gray-200 rounded" />
            </div>
          ))}
        </div>
        <div className="mt-3 h-10 bg-gray-100 rounded-xl" />
      </div>
    </div>
  );
}

function exportCostBreakdownCsv(breakdown: CostBreakdownItem[], totalCost: number) {
  const sep = ";";
  const rows = [
    ["Исполнитель", "Часов", "Оклад, ₽", "Стоимость, ₽"],
    ...breakdown.map((r) => [
      r.name,
      String(r.hours),
      r.salary > 0 ? String(r.salary) : "",
      r.cost > 0 ? String(Math.round(r.cost)) : "",
    ]),
    ["Итого", "", "", String(Math.round(totalCost))],
  ];
  const csv = "﻿" + rows.map((r) => r.join(sep)).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  triggerDownload(blob, "cost_breakdown.csv");
}

function CostBreakdownModal({
  breakdown, totalCost, onClose,
}: {
  breakdown: CostBreakdownItem[];
  totalCost: number;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-xl border w-full max-w-lg p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-800">Подробный расчёт стоимости</h3>
          <div className="flex items-center gap-2">
            <button
              onClick={() => exportCostBreakdownCsv(breakdown, totalCost)}
              className="text-xs text-blue-600 hover:text-blue-800 border border-blue-200 hover:border-blue-400 rounded px-2 py-1"
            >
              Скачать xlsx
            </button>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
          </div>
        </div>

        {breakdown.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-4">Оклады не настроены</p>
        ) : (
          <table className="w-full text-sm mb-4">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="text-left px-3 py-1.5">Исполнитель</th>
                <th className="text-right px-3 py-1.5">Часов</th>
                <th className="text-right px-3 py-1.5">Оклад, ₽</th>
                <th className="text-right px-3 py-1.5">Стоимость, ₽</th>
              </tr>
            </thead>
            <tbody>
              {breakdown.map((row) => (
                <tr key={row.name} className="border-b">
                  <td className="px-3 py-1.5">{row.name}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{row.hours}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums text-gray-500">
                    {row.salary > 0 ? fmtNum(row.salary) : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums font-medium">
                    {row.cost > 0 ? fmtNum(row.cost) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t-2 border-gray-300 bg-gray-50">
              <tr>
                <td colSpan={3} className="px-3 py-1.5 font-semibold text-right">Итого</td>
                <td className="px-3 py-1.5 text-right font-bold text-blue-700 tabular-nums">
                  {fmtRub(totalCost)}
                </td>
              </tr>
            </tfoot>
          </table>
        )}

        <p className="text-xs text-gray-400">
          Расчёт: оклад ÷ 160 ч/мес × плановые часы в прогнозе
        </p>
      </div>
    </div>
  );
}

function RoiModal({ totalCost, onClose }: { totalCost: number; onClose: () => void }) {
  const [revenueStr, setRevenueStr] = useState("");

  // Принимаем «1 200 000», «1200000», «1 200 000,50» — оставляем только цифры и разделитель
  const revenue = Number(revenueStr.replace(/\s/g, "").replace(",", ".")) || 0;
  const hasInput = revenueStr.trim() !== "" && revenue > 0;

  const profit = revenue - totalCost;
  const roiPct = totalCost > 0 ? (profit / totalCost) * 100 : 0;
  const positive = profit >= 0;

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-xl border w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-800">Расчёт ROI</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Доход от проекта, ₽
          </label>
          <input
            type="text"
            inputMode="numeric"
            autoFocus
            value={revenueStr}
            onChange={(e) => setRevenueStr(e.target.value)}
            placeholder="Например, 5 000 000"
            className="w-full px-3 py-2 border rounded-lg text-sm tabular-nums focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
        </div>

        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between px-3 py-2 bg-blue-50 rounded-lg">
            <span className="text-blue-500">Стоимость проекта</span>
            <span className="font-semibold text-blue-700 tabular-nums">{fmtRub(totalCost)}</span>
          </div>
          {hasInput && (
            <>
              <div className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg">
                <span className="text-gray-500">Прибыль</span>
                <span className={`font-semibold tabular-nums ${positive ? "text-green-700" : "text-red-700"}`}>
                  {profit >= 0 ? "+" : "−"}{fmtRub(Math.abs(profit))}
                </span>
              </div>
              <div className={`flex items-center justify-between px-3 py-2.5 rounded-lg ${positive ? "bg-green-50" : "bg-red-50"}`}>
                <span className={positive ? "text-green-600" : "text-red-600"}>ROI</span>
                <span className={`text-2xl font-bold tabular-nums ${positive ? "text-green-700" : "text-red-700"}`}>
                  {roiPct >= 0 ? "+" : "−"}{fmtNum(Math.abs(roiPct), 1)} %
                </span>
              </div>
            </>
          )}
        </div>

        <p className="mt-4 text-xs text-gray-400">
          ROI = (доход − стоимость проекта) ÷ стоимость проекта × 100 %
        </p>
      </div>
    </div>
  );
}
