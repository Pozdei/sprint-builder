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
import { VacationPanel } from "../components/VacationPanel";
import type { CostBreakdownItem, EpicForecastResponse, EpicForecastSnapshot, TaskDependency } from "../types/api";

function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

function fmtDate(iso: string) {
  const d = new Date(iso + "T12:00:00");
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "long", year: "numeric" });
}

function daysUntil(isoDate: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(isoDate + "T00:00:00");
  return Math.ceil((target.getTime() - today.getTime()) / 86400000);
}

export function EpicForecastPage({ isAdmin = false }: { isAdmin?: boolean }) {
  const [epicKey,    setEpicKey]    = useState("");
  const [startDate,  setStartDate]  = useState(todayISO());
  const [hoursPerDay, setHoursPerDay] = useState(8);

  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [result,   setResult]   = useState<EpicForecastResponse | null>(null);
  const [selectedKey,    setSelectedKey]    = useState<string | null>(null);
  const [showEstimates,  setShowEstimates]  = useState(false);

  const [showCostBreakdown, setShowCostBreakdown] = useState(false);
  const [showDeps,      setShowDeps]      = useState(false);
  const [showVacations, setShowVacations] = useState(false);
  const [epicDeps,      setEpicDeps]      = useState<TaskDependency[]>([]);
  const [snapshots,     setSnapshots]     = useState<EpicForecastSnapshot[]>([]);
  const [useHistory,    setUseHistory]    = useState(false);

  const handleForecast = async () => {
    const key = epicKey.trim().toUpperCase();
    if (!key) return;
    setLoading(true);
    setError(null);
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
    } catch (e: unknown) {
      if (e && typeof e === "object" && "response" in e) {
        const r = (e as { response?: { data?: { detail?: string } } }).response;
        setError(r?.data?.detail ?? "Ошибка");
      } else if (e instanceof Error) {
        setError(e.message);
      }
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
            onClick={handleForecast}
            disabled={loading || !epicKey.trim()}
            className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300
                       text-white font-semibold px-5 py-2 rounded-lg text-sm transition"
          >
            {loading ? "Считаю…" : "Построить прогноз"}
          </button>
          <label className="flex items-center gap-2 cursor-pointer select-none ml-1" title="Учитывать историю смен статусов при определении пройденных этапов">
            <div
              onClick={() => setUseHistory(v => !v)}
              className={`relative w-9 h-5 rounded-full transition-colors ${useHistory ? "bg-indigo-500" : "bg-gray-300"}`}
            >
              <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${useHistory ? "translate-x-4" : "translate-x-0.5"}`} />
            </div>
            <span className="text-sm text-gray-600">По истории статусов</span>
          </label>
        </div>

        {error && (
          <div className="mt-3 bg-red-50 border border-red-300 text-red-800 rounded-lg p-3 text-sm">
            {error}
          </div>
        )}
      </div>

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
                    {fmtDate(result.completion_date)}
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
                  { label: "Всего задач",     value: result.stats.total_issues },
                  { label: "Выполнено",        value: result.stats.done_issues,
                    sub: `${Math.round(result.stats.done_issues / Math.max(result.stats.total_issues,1)*100)}%` },
                  { label: "Осталось задач",  value: result.stats.total_issues - result.stats.done_issues,
                    sub: `${result.stats.remaining_work_items} эт. в расписании` },
                  { label: "Плановых часов",  value: `${result.stats.total_planned_hours} ч`,
                    warn: result.stats.default_hours_count > 0,
                    sub: result.stats.default_hours_count > 0
                      ? `${result.stats.default_hours_count} без оценки`
                      : "все оценены" },
                ].map((m) => (
                  <div key={m.label} className="bg-gray-50 rounded-xl px-3 py-2">
                    <div className="text-xs text-gray-500">{m.label}</div>
                    <div className={`text-xl font-bold ${m.warn ? "text-amber-600" : "text-gray-800"}`}>
                      {m.value}
                    </div>
                    {m.sub && (
                      <div className={`text-xs ${m.warn ? "text-amber-500" : "text-gray-400"}`}>
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
                    {result.stats.total_cost.toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₽
                  </span>
                  <span className="text-xs text-blue-400">по окладам команды</span>
                  {isAdmin && (
                    <button
                      onClick={() => setShowCostBreakdown(true)}
                      className="ml-auto text-xs text-blue-600 hover:text-blue-800 underline underline-offset-2"
                    >
                      Подробный расчёт
                    </button>
                  )}
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
                startDate={startDate}
                hoursPerDay={hoursPerDay}
                dependencies={epicDeps}
                onTaskClick={setSelectedKey}
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
        </>
      )}
    </div>
  );
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
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
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
                    {row.salary > 0 ? row.salary.toLocaleString("ru-RU") : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right tabular-nums font-medium">
                    {row.cost > 0 ? row.cost.toLocaleString("ru-RU", { maximumFractionDigits: 0 }) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t-2 border-gray-300 bg-gray-50">
              <tr>
                <td colSpan={3} className="px-3 py-1.5 font-semibold text-right">Итого</td>
                <td className="px-3 py-1.5 text-right font-bold text-blue-700 tabular-nums">
                  {totalCost.toLocaleString("ru-RU", { maximumFractionDigits: 0 })} ₽
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
