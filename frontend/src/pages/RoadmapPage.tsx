import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { getEpicPlans, getRoadmap, setEpicPlan, setTaskDetail } from "../api/roadmap-client";
import { useToast } from "../components/Toast";
import { extractError } from "../lib/api-error";
import { todayISO } from "../lib/format";
import { buildRoadmapGroups, type EpicPlanMap } from "../lib/roadmap";
import type { RoadmapGroupBy, RoadmapGroupOut, RoadmapTaskOut } from "../types/api";

const BOARD_DOT_COLORS = [
  "bg-indigo-500", "bg-sky-500", "bg-violet-500", "bg-rose-500", "bg-amber-500", "bg-teal-500",
];

function boardColor(board: string, allBoards: string[]): string {
  const idx = allBoards.indexOf(board);
  return BOARD_DOT_COLORS[idx % BOARD_DOT_COLORS.length] ?? "bg-gray-400";
}

const WIP_STRIPES = "repeating-linear-gradient(135deg, #f59e0b 0px, #f59e0b 6px, #fde68a 6px, #fde68a 12px)";
const NO_EPIC_FILTER = "__no_epic__";
const STATUS_LEGEND_KEY: Record<string, string> = {
  done: "legend.done", in_progress: "legend.inProgress", not_started: "legend.notStarted",
};

interface Tip { x: number; y: number; flip: boolean; title: string; lines: [string, string][] }

export function RoadmapPage() {
  const { t } = useTranslation("roadmap");
  const toast = useToast();

  const [tasks, setTasks] = useState<RoadmapTaskOut[] | null>(null);
  const [epicPlans, setEpicPlans] = useState<EpicPlanMap>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [groupBy, setGroupBy] = useState<RoadmapGroupBy>("epic");
  const [filter, setFilter] = useState("");
  const [boardFilter, setBoardFilter] = useState<Set<string> | null>(null); // null = все доски
  const [epicFilter, setEpicFilter] = useState(""); // "" = все эпики, NO_EPIC_FILTER = без эпика
  const [savingKey, setSavingKey] = useState<string | null>(null);
  const [savingPlanKey, setSavingPlanKey] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      // group_by запроса не важен — группируем на клиенте (см. lib/roadmap.ts),
      // задача несёт и epic_key, и detail одновременно.
      const [r, plans] = await Promise.all([getRoadmap("epic"), getEpicPlans()]);
      setTasks(r.tasks);
      setEpicPlans(Object.fromEntries(
        plans.map((p) => [p.epic_key, { start: p.planned_start, end: p.planned_end }]),
      ));
    } catch (e) {
      setError(extractError(e, t("error")));
    } finally {
      setLoading(false);
    }
  };

  // Построение тянет changelog по каждой задаче и может занять до минуты —
  // запускается только по кнопке, не при заходе на страницу.
  useEffect(() => {
    if (!loading) return;
    setElapsed(0);
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [loading]);

  const allBoards = useMemo(() => {
    const s = new Set<string>();
    (tasks ?? []).forEach((tk) => tk.boards.forEach((b) => s.add(b)));
    return Array.from(s).sort();
  }, [tasks]);

  const visibleTasks = useMemo(() => {
    if (!tasks) return [];
    if (!boardFilter) return tasks;
    return tasks.filter((tk) => tk.boards.some((b) => boardFilter.has(b)));
  }, [tasks, boardFilter]);

  const groups = useMemo(
    () => buildRoadmapGroups(visibleTasks, groupBy, epicPlans),
    [visibleTasks, groupBy, epicPlans],
  );

  const allEpics = useMemo(() => {
    const byKey = new Map<string, string>();
    visibleTasks.forEach((tk) => {
      if (tk.epic_key) byKey.set(tk.epic_key, `${tk.epic_key} ${tk.epic_summary ?? ""}`.trim());
    });
    return Array.from(byKey.entries())
      .map(([key, label]) => ({ key, label }))
      .sort((a, b) => a.key.localeCompare(b.key));
  }, [visibleTasks]);

  const filteredTableTasks = useMemo(() => {
    let result = visibleTasks;
    if (epicFilter === NO_EPIC_FILTER) result = result.filter((tk) => !tk.epic_key);
    else if (epicFilter) result = result.filter((tk) => tk.epic_key === epicFilter);

    const q = filter.trim().toLowerCase();
    if (q) {
      result = result.filter(
        (tk) => tk.key.toLowerCase().includes(q) || tk.summary.toLowerCase().includes(q),
      );
    }
    return result;
  }, [visibleTasks, filter, epicFilter]);

  const toggleBoard = (b: string) => {
    setBoardFilter((prev) => {
      const next = new Set(prev ?? allBoards);
      if (next.has(b)) next.delete(b); else next.add(b);
      return next.size === allBoards.length ? null : next;
    });
  };

  const saveDetail = async (task: RoadmapTaskOut, value: string) => {
    const trimmed = value.trim();
    if (trimmed === (task.detail ?? "")) return;
    setSavingKey(task.key);
    try {
      await setTaskDetail(task.key, trimmed);
      setTasks((prev) => prev?.map((tk) => (tk.key === task.key ? { ...tk, detail: trimmed || null } : tk)) ?? prev);
      toast.success(t("saved"));
    } catch (e) {
      toast.error(extractError(e, t("saveError")));
    } finally {
      setSavingKey(null);
    }
  };

  const savePlan = async (epicKey: string, plannedStart: string, plannedEnd: string) => {
    const prev = epicPlans[epicKey] ?? { start: "", end: "" };
    if (plannedStart === prev.start && plannedEnd === prev.end) return;
    setSavingPlanKey(epicKey);
    try {
      const result = await setEpicPlan(epicKey, plannedStart, plannedEnd);
      setEpicPlans((p) => {
        const next = { ...p };
        if (result) next[epicKey] = { start: result.planned_start, end: result.planned_end };
        else delete next[epicKey];
        return next;
      });
      toast.success(t("saved"));
    } catch (e) {
      toast.error(extractError(e, t("saveError")));
    } finally {
      setSavingPlanKey(null);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 py-8 space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 mb-1">{t("title")}</h1>
          <p className="text-gray-500 text-sm max-w-2xl">{t("subtitle")}</p>
        </div>
        {tasks !== null && (
          <div className="flex items-center gap-2 bg-white border rounded-xl p-1 shadow-sm">
            <span className="text-xs text-gray-400 pl-2">{t("groupBy.label")}</span>
            <div className="inline-flex rounded-lg overflow-hidden text-sm bg-gray-100 p-0.5">
              <button
                onClick={() => setGroupBy("epic")}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  groupBy === "epic" ? "bg-white text-indigo-700 shadow-sm" : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {t("groupBy.epic")}
              </button>
              <button
                onClick={() => setGroupBy("detail")}
                className={`px-3 py-1 rounded-md font-medium transition ${
                  groupBy === "detail" ? "bg-white text-indigo-700 shadow-sm" : "text-gray-500 hover:text-gray-700"
                }`}
              >
                {t("groupBy.detail")}
              </button>
            </div>
            <button
              onClick={load}
              disabled={loading}
              title={t("retry")}
              className="w-8 h-8 flex items-center justify-center text-base font-medium rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-50 transition"
            >
              ↻
            </button>
          </div>
        )}
      </div>

      {allBoards.length > 1 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-gray-400 font-medium">{t("table.boards")}</span>
          {allBoards.map((b) => {
            const active = !boardFilter || boardFilter.has(b);
            return (
              <button
                key={b}
                onClick={() => toggleBoard(b)}
                className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition ${
                  active
                    ? "border-gray-300 bg-white text-gray-700 shadow-sm"
                    : "border-gray-200 bg-gray-50 text-gray-400"
                }`}
              >
                <span className={`w-2 h-2 rounded-full ${boardColor(b, allBoards)}`} />
                {b}
              </button>
            );
          })}
        </div>
      )}

      {tasks === null && !loading && !error && (
        <div className="bg-white border rounded-xl p-12 text-center shadow-sm">
          <div className="w-12 h-12 mx-auto mb-4 rounded-full bg-indigo-50 flex items-center justify-center text-indigo-500 text-xl">
            ▤
          </div>
          <p className="text-sm text-gray-500 max-w-md mx-auto mb-5">{t("buildHint")}</p>
          <button
            onClick={load}
            className="px-5 py-2.5 text-sm font-medium bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 shadow-sm transition"
          >
            {t("build")}
          </button>
        </div>
      )}

      {loading && (
        <div className="bg-white border rounded-xl p-10 text-center text-sm text-gray-500 space-y-3 shadow-sm">
          <p>{t("loading")}</p>
          <div className="h-2 w-full max-w-sm mx-auto rounded-full overflow-hidden bg-gray-100">
            <div className="h-full w-full animate-pulse" style={{ background: WIP_STRIPES }} />
          </div>
          <p className="text-xs text-gray-400 tabular-nums">{t("loadingElapsed", { sec: elapsed })}</p>
        </div>
      )}

      {!loading && error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center shadow-sm">
          <p className="text-sm text-red-700 mb-3">{error}</p>
          <button
            onClick={load}
            className="px-3 py-1.5 text-sm font-medium bg-white border rounded-lg hover:bg-gray-50 transition"
          >
            {t("retry")}
          </button>
        </div>
      )}

      {!loading && !error && tasks && (
        <>
          <RoadmapTimeline
            groups={groups}
            emptyMessage={t(`empty.${groupBy}`)}
            groupBy={groupBy}
            onSavePlan={savePlan}
            savingPlanKey={savingPlanKey}
          />

          <TaskDetailTable
            tasks={filteredTableTasks}
            filter={filter}
            onFilterChange={setFilter}
            epics={allEpics}
            epicFilter={epicFilter}
            onEpicFilterChange={setEpicFilter}
            onSaveDetail={saveDetail}
            savingKey={savingKey}
          />
        </>
      )}
    </div>
  );
}

function LegendSwatch({ kind, label }: { kind: "done" | "wip" | "planned"; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[11px] text-gray-500">
      {kind === "done" && <span className="w-2.5 h-2.5 rounded-sm bg-emerald-500 inline-block shrink-0" />}
      {kind === "wip" && (
        <span className="w-2.5 h-2.5 rounded-sm inline-block shrink-0" style={{ background: WIP_STRIPES }} />
      )}
      {kind === "planned" && (
        <span className="w-2.5 h-1.5 rounded-full border-2 border-dashed border-indigo-400 inline-block shrink-0" />
      )}
      {label}
    </span>
  );
}

function RoadmapTimeline({
  groups, emptyMessage, groupBy, onSavePlan, savingPlanKey,
}: {
  groups: RoadmapGroupOut[];
  emptyMessage: string;
  groupBy: RoadmapGroupBy;
  onSavePlan: (epicKey: string, plannedStart: string, plannedEnd: string) => void;
  savingPlanKey: string | null;
}) {
  const { t } = useTranslation("roadmap");
  const rowH = groupBy === "epic" ? 68 : 44;
  const containerRef = useRef<HTMLDivElement>(null);
  const [tip, setTip] = useState<Tip | null>(null);

  const statusLabel = (g: RoadmapGroupOut) => t(STATUS_LEGEND_KEY[g.status] ?? "legend.notStarted");

  const showTip = (e: React.MouseEvent, title: string, lines: [string, string][]) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setTip({ x, y, flip: x > rect.width * 0.65, title, lines });
  };

  if (groups.length === 0) {
    return (
      <div className="bg-white border rounded-xl p-10 text-center text-sm text-gray-500">{emptyMessage}</div>
    );
  }

  const today = todayISO();
  // В диапазон таймлайна попадают и плановые даты — иначе бар запланированного,
  // но ещё не начатого эпика может оказаться за пределами видимой шкалы.
  const relevantDates = groups.flatMap((g) => [g.start, g.end, g.planned_start, g.planned_end].filter(Boolean));
  const minDate = relevantDates.length ? relevantDates.reduce((a, b) => (a < b ? a : b)) : today;
  const maxDate = relevantDates.concat(today).reduce((a, b) => (a > b ? a : b), today);

  const minMs = new Date(`${minDate}T00:00:00Z`).getTime();
  const maxMs = new Date(`${maxDate}T00:00:00Z`).getTime();
  const span = Math.max(maxMs - minMs, 86400000);
  const pct = (iso: string) => ((new Date(`${iso}T00:00:00Z`).getTime() - minMs) / span) * 100;

  const months: { pos: number; label: string; isCurrent: boolean }[] = [];
  const cur = new Date(minMs);
  cur.setUTCDate(1);
  const maxD = new Date(maxMs);
  const todayMonthKey = today.slice(0, 7);
  while (cur <= maxD) {
    months.push({
      pos: pct(cur.toISOString().slice(0, 10)),
      label: cur.toLocaleDateString("ru-RU", { month: "short", year: "2-digit" }),
      isCurrent: cur.toISOString().slice(0, 7) === todayMonthKey,
    });
    cur.setUTCMonth(cur.getUTCMonth() + 1);
  }

  const todayPos = pct(today);

  return (
    <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
      <div className="flex items-center justify-between gap-3 px-4 py-2.5 border-b bg-gray-50/70">
        <span className="text-xs font-semibold text-gray-600">{t("groupsLabel")}: {groups.length}</span>
        <div className="flex items-center gap-4">
          <LegendSwatch kind="done" label={t("legend.done")} />
          <LegendSwatch kind="wip" label={t("legend.inProgress")} />
          {groupBy === "epic" && <LegendSwatch kind="planned" label={t("legend.planned")} />}
        </div>
      </div>

      <div className="overflow-x-auto" ref={containerRef} onMouseLeave={() => setTip(null)}>
        <div className="min-w-[900px] relative">
          <div className="grid grid-cols-[280px_1fr] border-b">
            <div className="sticky left-0 z-10 bg-gray-50 border-r px-3 py-2" />
            <div className="relative h-8 bg-gray-50">
              {months.map((m, i) => (
                <div
                  key={i}
                  className={`absolute top-0 bottom-0 border-l pl-1.5 pt-1.5 text-[10px] ${
                    m.isCurrent ? "border-indigo-200 text-indigo-600 font-semibold" : "border-gray-200 text-gray-400"
                  }`}
                  style={{ left: `${m.pos}%` }}
                >
                  {m.label}
                </div>
              ))}
            </div>
          </div>

          {groups.map((g, i) => {
            const zebra = i % 2 === 1 ? "bg-gray-50/60" : "bg-white";
            const progressPct = g.total > 0 ? Math.round((g.done / g.total) * 100) : 0;
            return (
              <div key={g.key} className={`group grid grid-cols-[280px_1fr] border-b last:border-b-0 ${zebra}`}>
                <div
                  className={`sticky left-0 z-10 border-r px-3 py-2 min-w-0 flex flex-col justify-center group-hover:bg-indigo-50/60 transition-colors ${zebra}`}
                  style={{ minHeight: rowH }}
                >
                  <div className="text-xs font-semibold text-gray-800 truncate" title={g.label}>{g.label}</div>
                  <div className="text-[10px] text-gray-400 mt-0.5 truncate">
                    {g.done}/{g.total} · {g.boards.join(", ")}
                  </div>
                  {g.total > 0 && (
                    <div className="h-1 w-full max-w-[190px] bg-gray-100 rounded-full overflow-hidden mt-1">
                      <div
                        className="h-full bg-emerald-500 rounded-full transition-all"
                        style={{ width: `${progressPct}%` }}
                      />
                    </div>
                  )}
                  {groupBy === "epic" && (
                    // key включает плановые даты — при внешнем изменении (после сохранения/рефреша)
                    // компонент перемонтируется с новым начальным значением инпутов, без useEffect-синка.
                    <PlanEditor
                      key={`${g.key}:${g.planned_start}:${g.planned_end}`}
                      group={g}
                      onSave={onSavePlan}
                      saving={savingPlanKey === g.key}
                    />
                  )}
                </div>
                <div
                  className="relative group-hover:bg-indigo-50/40 transition-colors"
                  style={{ height: rowH }}
                >
                  {months.map((m, mi) => (
                    <div
                      key={mi}
                      className={`absolute top-0 bottom-0 border-l ${m.isCurrent ? "border-indigo-100" : "border-gray-100"}`}
                      style={{ left: `${m.pos}%` }}
                    />
                  ))}
                  {g.start && (
                    <div
                      className="absolute h-5 rounded shadow-sm cursor-default"
                      style={{
                        top: 8,
                        left: `${pct(g.start)}%`,
                        width: `${Math.max(pct(g.end || today) - pct(g.start), 0.8)}%`,
                        background: g.end ? "#10b981" : WIP_STRIPES,
                      }}
                      onMouseEnter={(e) => showTip(e, g.label, [
                        [t("tooltip.status"), statusLabel(g)],
                        [t("tooltip.period"), `${g.start} → ${g.end || t("tooltip.fillManually")}`],
                        [t("tooltip.tasks"), `${g.done}/${g.total}`],
                        [t("tooltip.boards"), g.boards.join(", ")],
                      ])}
                      onMouseMove={(e) => showTip(e, g.label, [
                        [t("tooltip.status"), statusLabel(g)],
                        [t("tooltip.period"), `${g.start} → ${g.end || t("tooltip.fillManually")}`],
                        [t("tooltip.tasks"), `${g.done}/${g.total}`],
                        [t("tooltip.boards"), g.boards.join(", ")],
                      ])}
                    />
                  )}
                  {groupBy === "epic" && g.planned_start && g.planned_end && (
                    <div
                      className="absolute h-2.5 rounded-full border-2 border-dashed border-indigo-400 bg-indigo-50/80 cursor-default"
                      style={{
                        top: 38,
                        left: `${pct(g.planned_start)}%`,
                        width: `${Math.max(pct(g.planned_end) - pct(g.planned_start), 0.8)}%`,
                      }}
                      onMouseEnter={(e) => showTip(e, g.label, [
                        [t("tooltip.status"), t("legend.planned")],
                        [t("tooltip.period"), `${g.planned_start} → ${g.planned_end}`],
                      ])}
                      onMouseMove={(e) => showTip(e, g.label, [
                        [t("tooltip.status"), t("legend.planned")],
                        [t("tooltip.period"), `${g.planned_start} → ${g.planned_end}`],
                      ])}
                    />
                  )}
                  {groupBy === "epic" && (g.planned_start || g.planned_end) && !(g.planned_start && g.planned_end) && (
                    // Задана только одна из дат — рисуем метку-ромб вместо бара (тянуть его
                    // не от чего): планового старта без конца или конца без старта.
                    <div
                      className="absolute w-2.5 h-2.5 rotate-45 border-2 border-indigo-400 bg-indigo-100 shadow-sm cursor-default"
                      style={{ top: 36, left: `calc(${pct(g.planned_start || g.planned_end)}% - 5px)` }}
                      onMouseEnter={(e) => showTip(e, g.label, [
                        [t("tooltip.status"), t("legend.planned")],
                        [
                          g.planned_start ? t("plan.startTitle") : t("plan.endTitle"),
                          g.planned_start || g.planned_end,
                        ],
                      ])}
                      onMouseMove={(e) => showTip(e, g.label, [
                        [t("tooltip.status"), t("legend.planned")],
                        [
                          g.planned_start ? t("plan.startTitle") : t("plan.endTitle"),
                          g.planned_start || g.planned_end,
                        ],
                      ])}
                    />
                  )}
                </div>
              </div>
            );
          })}

          <div
            className="absolute top-8 bottom-0 border-l border-dashed border-red-400 pointer-events-none z-[5]"
            style={{ left: `calc(280px + (100% - 280px) * ${todayPos / 100})` }}
          >
            <span className="absolute -top-[18px] left-1 text-[9px] font-medium text-red-500 whitespace-nowrap bg-white/90 px-1 rounded">
              {t("today")}
            </span>
          </div>

          {tip && (
            <div
              className="absolute pointer-events-none z-20 bg-gray-900 text-white text-xs rounded-lg p-2.5 shadow-xl max-w-xs"
              style={{
                left: tip.x + 12,
                top: tip.y - 10,
                transform: tip.flip ? "translateX(-110%)" : undefined,
              }}
            >
              <div className="font-semibold mb-1">{tip.title}</div>
              <div className="space-y-0.5">
                {tip.lines.map(([k, v]) => (
                  <div key={k} className="text-gray-300">
                    {k}: <span className="text-white">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PlanEditor({
  group, onSave, saving,
}: {
  group: RoadmapGroupOut;
  onSave: (epicKey: string, plannedStart: string, plannedEnd: string) => void;
  saving: boolean;
}) {
  const { t } = useTranslation("roadmap");
  const [start, setStart] = useState(group.planned_start);
  const [end, setEnd] = useState(group.planned_end);
  const commit = () => onSave(group.key, start, end);

  const inputCls = "text-[10px] border border-gray-200 rounded px-1 py-0.5 w-[108px] bg-white "
    + "hover:border-gray-300 focus:ring-1 focus:ring-indigo-400 focus:border-indigo-400 outline-none "
    + "disabled:opacity-50 transition";

  return (
    <div className="flex items-center gap-1 mt-1">
      <input
        type="date"
        value={start}
        onChange={(e) => setStart(e.target.value)}
        onBlur={commit}
        disabled={saving}
        title={t("plan.startTitle")}
        className={inputCls}
      />
      <span className="text-[10px] text-gray-300">→</span>
      <input
        type="date"
        value={end}
        min={start || undefined}
        onChange={(e) => setEnd(e.target.value)}
        onBlur={commit}
        disabled={saving}
        title={t("plan.endTitle")}
        className={inputCls}
      />
    </div>
  );
}

function TaskDetailTable({
  tasks, filter, onFilterChange, epics, epicFilter, onEpicFilterChange, onSaveDetail, savingKey,
}: {
  tasks: RoadmapTaskOut[];
  filter: string;
  onFilterChange: (v: string) => void;
  epics: { key: string; label: string }[];
  epicFilter: string;
  onEpicFilterChange: (v: string) => void;
  onSaveDetail: (task: RoadmapTaskOut, value: string) => void;
  savingKey: string | null;
}) {
  const { t } = useTranslation("roadmap");
  return (
    <div className="bg-white border rounded-xl overflow-hidden shadow-sm">
      <div className="flex items-center justify-between gap-4 px-4 py-3 border-b bg-gray-50/70 flex-wrap">
        <div>
          <h2 className="text-sm font-semibold text-gray-800">
            {t("table.title")} <span className="text-gray-400 font-normal">· {tasks.length}</span>
          </h2>
          <p className="text-xs text-gray-500 mt-0.5">{t("table.subtitle")}</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={epicFilter}
            onChange={(e) => onEpicFilterChange(e.target.value)}
            className="px-2 py-1.5 text-sm border rounded-lg bg-white text-gray-700 max-w-[220px]"
          >
            <option value="">{t("table.epicFilterAll")}</option>
            <option value={NO_EPIC_FILTER}>{t("table.epicFilterNone")}</option>
            {epics.map((e) => (
              <option key={e.key} value={e.key} title={e.label}>{e.label}</option>
            ))}
          </select>
          <input
            value={filter}
            onChange={(e) => onFilterChange(e.target.value)}
            placeholder={t("table.filterPlaceholder")}
            className="px-3 py-1.5 text-sm border rounded-lg w-64"
          />
        </div>
      </div>
      <div className="overflow-x-auto max-h-[480px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 sticky top-0 z-10">
            <tr>
              <th className="text-left px-3 py-2 font-semibold text-gray-500 text-[11px] uppercase tracking-wide">{t("table.key")}</th>
              <th className="text-left px-3 py-2 font-semibold text-gray-500 text-[11px] uppercase tracking-wide">{t("table.summary")}</th>
              <th className="text-left px-3 py-2 font-semibold text-gray-500 text-[11px] uppercase tracking-wide">{t("table.boards")}</th>
              <th className="text-left px-3 py-2 font-semibold text-gray-500 text-[11px] uppercase tracking-wide">{t("table.epic")}</th>
              <th className="text-left px-3 py-2 font-semibold text-gray-500 text-[11px] uppercase tracking-wide">{t("table.start")}</th>
              <th className="text-left px-3 py-2 font-semibold text-gray-500 text-[11px] uppercase tracking-wide">{t("table.end")}</th>
              <th className="text-left px-3 py-2 font-semibold text-gray-500 text-[11px] uppercase tracking-wide w-56">{t("table.detail")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {tasks.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-8 text-center text-sm text-gray-400">
                  {t("table.empty")}
                </td>
              </tr>
            )}
            {tasks.map((tk) => (
              // key включает detail — при внешнем изменении (после сохранения/рефреша)
              // строка перемонтируется с новым начальным значением инпута, без useEffect-синка.
              <TaskDetailRow key={`${tk.key}:${tk.detail ?? ""}`} task={tk} onSave={onSaveDetail} saving={savingKey === tk.key} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TaskDetailRow({
  task, onSave, saving,
}: {
  task: RoadmapTaskOut;
  onSave: (task: RoadmapTaskOut, value: string) => void;
  saving: boolean;
}) {
  const { t } = useTranslation("roadmap");
  const [value, setValue] = useState(task.detail ?? "");

  const statusDot = task.end ? "bg-emerald-500" : task.start ? "bg-amber-500" : "bg-gray-300";
  const statusTitle = task.end ? t("legend.done") : task.start ? t("legend.inProgress") : t("legend.notStarted");

  return (
    <tr className="even:bg-gray-50/60 hover:bg-indigo-50/50 transition-colors">
      <td className="px-3 py-1.5">
        <a
          href={task.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1.5 text-indigo-600 hover:underline font-medium"
        >
          <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${statusDot}`} title={statusTitle} />
          {task.key}
        </a>
      </td>
      <td className="px-3 py-1.5 text-gray-700 max-w-xs truncate" title={task.summary}>{task.summary}</td>
      <td className="px-3 py-1.5 text-gray-500 text-xs whitespace-nowrap">{task.boards.join(", ")}</td>
      <td className="px-3 py-1.5 text-gray-500 text-xs max-w-[160px] truncate" title={task.epic_summary ?? undefined}>
        {task.epic_key ?? <span className="text-gray-300">{t("table.noEpic")}</span>}
      </td>
      <td className="px-3 py-1.5 text-gray-500 text-xs whitespace-nowrap">{task.start || <span className="text-gray-300">—</span>}</td>
      <td className="px-3 py-1.5 text-gray-500 text-xs whitespace-nowrap">{task.end || <span className="text-gray-300">—</span>}</td>
      <td className="px-3 py-1.5">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onBlur={() => onSave(task, value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") (e.target as HTMLInputElement).blur();
          }}
          placeholder={t("table.detailPlaceholder")}
          disabled={saving}
          className="w-full px-2 py-1 text-xs border rounded disabled:opacity-50 focus:ring-1 focus:ring-indigo-400 focus:border-indigo-400 outline-none transition"
        />
      </td>
    </tr>
  );
}
