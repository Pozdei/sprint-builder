import { useEffect, useMemo, useState } from "react";
import {
  approveSprint, reopenSprint,
  closeSprint,
  deleteGanttSnapshot,
  deleteSprint,
  downloadSprintXlsx,
  fetchGantt,
  fetchSprintDependencies,
  getGanttSnapshot,
  getSprint,
  listGanttSnapshots,
  listSprints,
  saveGanttSnapshot,
} from "../api/client";
import { extractError } from "../lib/api-error";
import { ClosedSprintView } from "../components/ClosedSprintView";
import { useToast } from "../components/Toast";
import { GanttChart } from "../components/GanttChart";
import { GanttSnapshotBanner, GanttSnapshotControls } from "../components/GanttSnapshotControls";
import { OwnerStats } from "../components/OwnerStats";
import { SprintTable } from "../components/SprintTable";
import { StandupModal } from "../components/StandupModal";
import { useGanttSnapshots, type GanttSnapshotApi } from "../hooks/useGanttSnapshots";
import { useRootTasks } from "../hooks/useRootTasks";
import { fmtDateTime } from "../lib/format";
import type {
  GanttItem,
  SprintOut, SprintStatus, SprintSummary,
} from "../types/api";

export function HistoryPage() {
  const [items, setItems] = useState<SprintSummary[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const loadList = async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await listSprints();
      setItems(r);
    } catch (e) {
      setError(extractError(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadList();
  }, []);

  const toggleExpand = (id: number) => {
    setExpandedId(expandedId === id ? null : id);
  };

  if (loading) {
    return <div className="text-center text-gray-500 mt-20">Загрузка истории…</div>;
  }
  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-6">
        <div className="bg-red-50 border border-red-300 text-red-800 rounded-lg p-3">
          {error}
        </div>
      </div>
    );
  }
  if (!items || items.length === 0) {
    return (
      <div className="text-center text-gray-500 mt-20">
        Нет сохранённых спринтов. Сформируй спринт на вкладке «Спринт».
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
      <h1 className="text-lg font-semibold text-gray-800 mb-4">История спринтов</h1>

      <div className="bg-white rounded-lg border shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 border-b">
            <tr>
              <th className="text-left px-4 py-2 font-semibold">№</th>
              <th className="text-left px-4 py-2 font-semibold">Статус</th>
              <th className="text-left px-4 py-2 font-semibold">Создан</th>
              <th className="text-left px-4 py-2 font-semibold">Утверждён</th>
              <th className="text-left px-4 py-2 font-semibold">Закрыт</th>
              <th className="text-left px-4 py-2 font-semibold">Задач</th>
              <th className="w-10"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((s) => (
              <SprintRow
                key={s.id}
                summary={s}
                expanded={expandedId === s.id}
                onToggle={() => toggleExpand(s.id)}
                onChanged={loadList}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: SprintStatus }) {
  const map: Record<SprintStatus, { bg: string; text: string; label: string }> = {
    draft:    { bg: "bg-yellow-100", text: "text-yellow-800", label: "draft" },
    approved: { bg: "bg-green-100",  text: "text-green-800",  label: "approved" },
    closed:   { bg: "bg-gray-200",   text: "text-gray-800",   label: "closed" },
  };
  const s = map[status];
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-semibold ${s.bg} ${s.text}`}>
      {s.label}
    </span>
  );
}

interface RowProps {
  summary: SprintSummary;
  expanded: boolean;
  onToggle: () => void;
  onChanged: () => void;
}

function SprintRow({ summary, expanded, onToggle, onChanged }: RowProps) {
  const toast = useToast();
  const [detail, setDetail] = useState<SprintOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"approve" | "reopen" | "delete" | "download" | "close" | null>(null);
  const [showStandup, setShowStandup] = useState(false);

  // Гант
  const [ganttDate, setGanttDate] = useState<string>(() => {
    const d = new Date();
    return d.toISOString().slice(0, 10);
  });
  const [hoursPerDay, setHoursPerDay] = useState(8);
  const [ganttItems, setGanttItems] = useState<GanttItem[] | null>(null);
  const [ganttLoading, setGanttLoading] = useState(false);
  const [showGantt, setShowGantt] = useState(false);
  const rootTasksHook = useRootTasks(detail ? `sprint-${detail.sprint_num}` : null);

  // Снимки Ганта — единый механизм с прогнозом по эпику (см. GanttSnapshotControls/useGanttSnapshots)
  const sprintId = detail?.id;
  const snapshotApi = useMemo<GanttSnapshotApi>(() => ({
    list: () => (sprintId != null ? listGanttSnapshots(sprintId) : Promise.resolve([])),
    create: (s, h, items, label) =>
      sprintId != null ? saveGanttSnapshot(sprintId, s, h, items, label) : Promise.reject(new Error("no sprint")),
    get: (id) => (sprintId != null ? getGanttSnapshot(sprintId, id) : Promise.reject(new Error("no sprint"))),
    remove: (id) => (sprintId != null ? deleteGanttSnapshot(sprintId, id) : Promise.reject(new Error("no sprint"))),
  }), [sprintId]);
  const snap = useGanttSnapshots(snapshotApi, sprintId ?? null);

  useEffect(() => {
    if (!expanded || detail) return;
    setLoading(true);
    setLoadError(null);
    getSprint(summary.id)
      .then(setDetail)
      .catch((e) => setLoadError(extractError(e)))
      .finally(() => setLoading(false));
  }, [expanded, summary.id, detail]);

  const handleApprove = async () => {
    if (!detail) return;
    let depWarning = "";
    try {
      const deps = await fetchSprintDependencies(detail.id);
      if (deps.length > 0) {
        depWarning = `\n\n⚠ В спринте ${deps.length} FS-завис${deps.length === 1 ? "имость" : "имостей"} между задачами — убедитесь, что расписание корректно.`;
      }
    } catch {
      // не критично
    }
    const ok = window.confirm(
      `Утвердить Sprint ${detail.sprint_num}?\n\n` +
      `В Jira уже должен существовать Sprint ${detail.sprint_num}.` +
      depWarning
    );
    if (!ok) return;
    setBusy("approve");
    try {
      const updated = await approveSprint(detail.id);
      setDetail(updated);
      onChanged();
      toast.success(`Sprint ${updated.sprint_num} утверждён`);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setBusy(null);
    }
  };

  const handleReopen = async () => {
    if (!detail) return;
    const ok = window.confirm(
      `Вернуть Sprint ${detail.sprint_num} в драфт?\n\n` +
      `Статус изменится на draft, дата утверждения будет сброшена.`
    );
    if (!ok) return;
    setBusy("reopen");
    try {
      const updated = await reopenSprint(detail.id);
      setDetail(updated);
      onChanged();
      toast.success(`Sprint ${updated.sprint_num} возвращён в драфт`);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setBusy(null);
    }
  };

  const handleClose = async () => {
    if (!detail) return;
    const ok = window.confirm(
      `Закрыть Sprint ${detail.sprint_num}?\n\n` +
      `В Jira спринт уже должен быть закрыт (state=closed). ` +
      `Будут получены статусы задач и список "врывов" — это может занять минуту.`
    );
    if (!ok) return;
    setBusy("close");
    try {
      const updated = await closeSprint(detail.id);
      setDetail(updated);
      onChanged();
      toast.success(`Sprint ${updated.sprint_num} закрыт`);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setBusy(null);
    }
  };

  const handleDelete = async () => {
    if (!detail) return;
    const ok = window.confirm(`Удалить Sprint ${detail.sprint_num}?`);
    if (!ok) return;
    setBusy("delete");
    try {
      await deleteSprint(detail.id);
      toast.success(`Sprint ${detail.sprint_num} удалён`);
      onChanged();
    } catch (e) {
      toast.error(extractError(e));
      setBusy(null);
    }
  };

  const handleDownload = async () => {
    if (!detail) return;
    setBusy("download");
    try {
      const payload: Parameters<typeof downloadSprintXlsx>[0] = {
        allocated: detail.tasks,
        owner_stats: detail.owner_stats,
        max_sprint_num: detail.sprint_num,
      };
      if (detail.status === "closed") {
        payload.closed_tasks = detail.closed_tasks;
        payload.terminal_statuses =
          (detail.config_snapshot.terminal_statuses as string[] | undefined) ?? [];
        if (detail.intrusions && detail.intrusions.length > 0) {
          payload.intrusions = detail.intrusions;
        }
      }
      await downloadSprintXlsx(payload);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setBusy(null);
    }
  };

  const handleLoadGantt = async () => {
    if (!detail) return;
    setGanttLoading(true);
    try {
      const items = await fetchGantt(detail.id, ganttDate, hoursPerDay);
      setGanttItems(items);
      setShowGantt(true);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setGanttLoading(false);
    }
  };

  const handleSaveSnapshot = async () => {
    if (!ganttItems) return;
    try {
      const summary = await snap.save(ganttDate, hoursPerDay, ganttItems);
      toast.success(`Снимок Ганта сохранён (${fmtDateTime(summary.captured_at)})`);
    } catch (e) {
      toast.error(extractError(e));
    }
  };

  const handleSnapshotChange = async (value: string) => {
    try {
      await snap.select(value === "current" ? "current" : Number(value));
    } catch (e) {
      toast.error(extractError(e));
    }
  };

  const handleDeleteSnapshot = async (id: number) => {
    const ok = window.confirm("Удалить этот снимок Ганта?");
    if (!ok) return;
    try {
      await snap.remove(id);
      toast.success("Снимок удалён");
    } catch (e) {
      toast.error(extractError(e));
    }
  };

  const isHistorical = snap.selectedId !== "current";
  const displayedItems = isHistorical ? snap.detail?.gantt_items ?? null : ganttItems;
  const displayedStart = isHistorical ? snap.detail?.gantt_start ?? ganttDate : ganttDate;
  const displayedHours = isHistorical ? snap.detail?.hours_per_day ?? hoursPerDay : hoursPerDay;

  const isDraft = summary.status === "draft";
  const isApproved = summary.status === "approved";
  const isClosed = summary.status === "closed";

  return (
    <>
      <tr
        className="border-b hover:bg-gray-50 cursor-pointer"
        onClick={onToggle}
      >
        <td className="px-4 py-2 font-mono">{summary.sprint_num}</td>
        <td className="px-4 py-2">
          <StatusBadge status={summary.status} />
        </td>
        <td className="px-4 py-2 text-gray-600">{fmtDateTime(summary.created_at)}</td>
        <td className="px-4 py-2 text-gray-600">
          {summary.approved_at ? fmtDateTime(summary.approved_at) : "—"}
        </td>
        <td className="px-4 py-2 text-gray-600">
          {summary.closed_at ? fmtDateTime(summary.closed_at) : "—"}
        </td>
        <td className="px-4 py-2">{summary.tasks_count}</td>
        <td className="px-4 py-2 text-gray-400">{expanded ? "▾" : "▸"}</td>
      </tr>

      {expanded && (
        <tr>
          <td colSpan={7} className="p-0">
            <div className="bg-gray-50 p-4 border-t">
              {loading && <div className="text-gray-500">Загрузка…</div>}
              {loadError && (
                <div className="bg-red-50 border border-red-300 text-red-800 rounded p-3 mb-3">
                  {loadError}
                </div>
              )}
              {detail && (
                <>
                  <div className="flex gap-2 mb-3">
                    <button
                      onClick={handleDownload}
                      disabled={busy !== null}
                      className="bg-green-700 hover:bg-green-800 disabled:bg-gray-300 text-white px-3 py-1.5 rounded text-sm font-semibold"
                    >
                      {busy === "download" ? "Скачиваю…" : "Скачать xlsx"}
                    </button>
                    {isDraft && (
                      <>
                        <button
                          onClick={handleApprove}
                          disabled={busy !== null}
                          className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-300 text-white px-3 py-1.5 rounded text-sm font-semibold"
                        >
                          {busy === "approve" ? "Утверждаю…" : "Утвердить"}
                        </button>
                        <button
                          onClick={handleDelete}
                          disabled={busy !== null}
                          className="bg-red-600 hover:bg-red-700 disabled:bg-gray-300 text-white px-3 py-1.5 rounded text-sm font-semibold"
                        >
                          {busy === "delete" ? "Удаляю…" : "Удалить"}
                        </button>
                      </>
                    )}
                    {isApproved && (
                      <>
                        <button
                          onClick={handleReopen}
                          disabled={busy !== null}
                          className="bg-amber-500 hover:bg-amber-600 disabled:bg-gray-300 text-white px-3 py-1.5 rounded text-sm font-semibold"
                        >
                          {busy === "reopen" ? "Возвращаю…" : "Вернуть в драфт"}
                        </button>
                        <button
                          onClick={() => setShowStandup(true)}
                          disabled={busy !== null}
                          className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white px-3 py-1.5 rounded text-sm font-semibold"
                        >
                          📋 Stand-up
                        </button>
                        <button
                          onClick={handleClose}
                          disabled={busy !== null}
                          className="bg-gray-700 hover:bg-gray-800 disabled:bg-gray-300 text-white px-3 py-1.5 rounded text-sm font-semibold"
                        >
                          {busy === "close" ? "Закрываю…" : "Закрыть спринт"}
                        </button>
                      </>
                    )}
                  </div>

                  {showStandup && (
                    <StandupModal
                      sprint={detail}
                      onClose={() => setShowStandup(false)}
                    />
                  )}

                  <OwnerStats stats={detail.owner_stats} />

                  {/* Секция Гант */}
                  <div className="mb-4">
                    <div className="flex items-center gap-3 flex-wrap">
                      <button
                        onClick={() => setShowGantt((v) => !v)}
                        className="text-sm font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
                      >
                        {showGantt ? "▾" : "▸"} Диаграмма Ганта
                      </button>
                      {showGantt && (
                        <>
                          <label className="text-sm text-gray-600 flex items-center gap-1.5">
                            Старт:
                            <input
                              type="date"
                              value={ganttDate}
                              onChange={(e) => { setGanttDate(e.target.value); setGanttItems(null); }}
                              className="border rounded px-2 py-0.5 text-sm"
                            />
                          </label>
                          <label className="text-sm text-gray-600 flex items-center gap-1.5">
                            Ч/день:
                            <input
                              type="number"
                              min={1} max={24} step={1}
                              value={hoursPerDay}
                              onChange={(e) => { setHoursPerDay(Number(e.target.value)); setGanttItems(null); }}
                              onWheel={(e) => e.currentTarget.blur()}
                              className="border rounded px-2 py-0.5 text-sm w-16"
                            />
                          </label>
                          <button
                            onClick={handleLoadGantt}
                            disabled={ganttLoading}
                            className="bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-300 text-white px-3 py-1 rounded text-sm font-semibold"
                          >
                            {ganttLoading ? "Считаю…" : "Построить"}
                          </button>
                          <GanttSnapshotControls
                            snapshots={snap.snapshots}
                            selectedId={snap.selectedId}
                            saving={snap.saving}
                            canSave={!!ganttItems}
                            onSave={handleSaveSnapshot}
                            onSelect={handleSnapshotChange}
                          />
                        </>
                      )}
                    </div>

                    {showGantt && isHistorical && (
                      <GanttSnapshotBanner
                        snapshot={snap.detail}
                        onDelete={() => handleDeleteSnapshot(snap.selectedId as number)}
                        onReturn={() => handleSnapshotChange("current")}
                      />
                    )}

                    {showGantt && snap.detailLoading && (
                      <div className="mt-3 text-gray-500 text-sm">Загрузка снимка…</div>
                    )}

                    {showGantt && !snap.detailLoading && displayedItems && displayedItems.length > 0 && (
                      <div className="mt-3">
                        <GanttChart
                          items={displayedItems}
                          startDate={displayedStart}
                          hoursPerDay={displayedHours}
                          rootTasks={isHistorical ? {} : rootTasksHook.map}
                        />
                      </div>
                    )}

                  </div>

                  <SprintTable tasks={detail.tasks} />

                  {isClosed && <ClosedSprintView sprint={detail} />}
                </>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}