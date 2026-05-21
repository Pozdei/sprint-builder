import { useEffect, useState } from "react";
import {
  approveSprint,
  closeSprint,
  deleteSprint,
  downloadSprintXlsx,
  fetchGantt,
  fetchSprintDependencies,
  getSprint,
  listSprints,
} from "../api/client";
import { ClosedSprintView } from "../components/ClosedSprintView";
import { GanttChart } from "../components/GanttChart";
import { OwnerStats } from "../components/OwnerStats";
import { SprintTable } from "../components/SprintTable";
import { StandupModal } from "../components/StandupModal";
import type { GanttItem, SprintOut, SprintStatus, SprintSummary } from "../types/api";

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
  const [detail, setDetail] = useState<SprintOut | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"approve" | "delete" | "download" | "close" | null>(null);
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

  useEffect(() => {
    if (!expanded || detail) return;
    setLoading(true);
    setError(null);
    getSprint(summary.id)
      .then(setDetail)
      .catch((e) => setError(extractError(e)))
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
    setError(null);
    try {
      const updated = await approveSprint(detail.id);
      setDetail(updated);
      onChanged();
    } catch (e) {
      setError(extractError(e));
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
    setError(null);
    try {
      const updated = await closeSprint(detail.id);
      setDetail(updated);
      onChanged();
    } catch (e) {
      setError(extractError(e));
    } finally {
      setBusy(null);
    }
  };

  const handleDelete = async () => {
    if (!detail) return;
    const ok = window.confirm(`Удалить Sprint ${detail.sprint_num}?`);
    if (!ok) return;
    setBusy("delete");
    setError(null);
    try {
      await deleteSprint(detail.id);
      onChanged();
    } catch (e) {
      setError(extractError(e));
      setBusy(null);
    }
  };

  const handleDownload = async () => {
    if (!detail) return;
    setBusy("download");
    setError(null);
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
      setError(extractError(e));
    } finally {
      setBusy(null);
    }
  };

  const handleLoadGantt = async () => {
    if (!detail) return;
    setGanttLoading(true);
    setError(null);
    try {
      const items = await fetchGantt(detail.id, ganttDate, hoursPerDay);
      setGanttItems(items);
      setShowGantt(true);
    } catch (e) {
      setError(extractError(e));
    } finally {
      setGanttLoading(false);
    }
  };

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
        <td className="px-4 py-2 text-gray-600">{formatDate(summary.created_at)}</td>
        <td className="px-4 py-2 text-gray-600">
          {summary.approved_at ? formatDate(summary.approved_at) : "—"}
        </td>
        <td className="px-4 py-2 text-gray-600">
          {summary.closed_at ? formatDate(summary.closed_at) : "—"}
        </td>
        <td className="px-4 py-2">{summary.tasks_count}</td>
        <td className="px-4 py-2 text-gray-400">{expanded ? "▾" : "▸"}</td>
      </tr>

      {expanded && (
        <tr>
          <td colSpan={7} className="p-0">
            <div className="bg-gray-50 p-4 border-t">
              {loading && <div className="text-gray-500">Загрузка…</div>}
              {error && (
                <div className="bg-red-50 border border-red-300 text-red-800 rounded p-3 mb-3">
                  {error}
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
                        </>
                      )}
                    </div>

                    {showGantt && ganttItems && ganttItems.length > 0 && (
                      <div className="mt-3">
                        <GanttChart
                          items={ganttItems}
                          startDate={ganttDate}
                          hoursPerDay={hoursPerDay}
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

const _dtFmt = new Intl.DateTimeFormat("ru-RU", {
  year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit",
});

function formatDate(iso: string): string {
  return _dtFmt.format(new Date(iso));
}

function extractError(e: unknown): string {
  if (e && typeof e === "object" && "response" in e) {
    const r = (e as { response?: { data?: { detail?: string } } }).response;
    if (r?.data?.detail) return r.data.detail;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}
