import { useState } from "react";
import { fetchEpicForecast } from "../api/client";
import { EstimateModal } from "../components/EstimateModal";
import { GanttChart } from "../components/GanttChart";
import { TaskPipelineModal } from "../components/TaskPipelineModal";
import type { EpicForecastResponse } from "../types/api";

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

export function EpicForecastPage() {
  const [epicKey,    setEpicKey]    = useState("");
  const [startDate,  setStartDate]  = useState(todayISO());
  const [hoursPerDay, setHoursPerDay] = useState(8);

  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState<string | null>(null);
  const [result,   setResult]   = useState<EpicForecastResponse | null>(null);
  const [selectedKey,    setSelectedKey]    = useState<string | null>(null);
  const [showEstimates,  setShowEstimates]  = useState(false);

  const handleForecast = async () => {
    const key = epicKey.trim().toUpperCase();
    if (!key) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await fetchEpicForecast(key, startDate, hoursPerDay);
      setResult(data);
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
              {/* Шапка с кнопкой */}
              <div className="flex items-center justify-between mb-2">
                <p className="text-xs text-gray-400">
                  Клик — все этапы · двойной — Jira
                </p>
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
              <GanttChart
                items={result.gantt_items}
                startDate={startDate}
                hoursPerDay={hoursPerDay}
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

          {showEstimates && result && (
            <EstimateModal
              items={result.gantt_items}
              onClose={() => setShowEstimates(false)}
              onSaved={() => {
                setShowEstimates(false);
                // Пересчитываем прогноз с теми же параметрами
                handleForecast();
              }}
            />
          )}
        </>
      )}
    </div>
  );
}
