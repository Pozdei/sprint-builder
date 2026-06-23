import { useEffect, useMemo, useState } from "react";
import {
  approveSprint,
  buildAndSaveSprint,
  downloadCandidatesXlsx,
  downloadSprintXlsx,
  fetchCandidates,
  getDefaultConfig,
  setSprintTasks,
} from "../api/client";
import { DiagnosticsPanel } from "../components/DiagnosticsPanel";
import { JiraFieldEditor } from "../components/JiraFieldEditor";
import { OwnerStats } from "../components/OwnerStats";
import { SprintComposer } from "../components/SprintComposer";
import type { AssignablePerson } from "../components/SprintTable";
import { SprintTable } from "../components/SprintTable";
import { useToast } from "../components/Toast";
import type { IssueFieldsUpdate } from "../api/jira-client";
import { extractError } from "../lib/api-error";
import type { OwnerStat, SprintOut, TaskOut } from "../types/api";

interface Props {
  jiraReady: boolean;
}

function IconRefresh() {
  return (
    <svg viewBox="0 0 24 24" width={16} height={16} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 12a9 9 0 0 1 15.5-6.36M21 12a9 9 0 0 1-15.5 6.36" />
      <path d="M18 3v4.5h-4.5M6 21v-4.5h4.5" />
    </svg>
  );
}
function IconDownload() {
  return (
    <svg viewBox="0 0 24 24" width={16} height={16} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3v12m0 0-4-4m4 4 4-4" />
      <path d="M4 19h16" />
    </svg>
  );
}
function IconBolt() {
  return (
    <svg viewBox="0 0 24 24" width={16} height={16} fill="currentColor">
      <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" />
    </svg>
  );
}
function IconEdit() {
  return (
    <svg viewBox="0 0 24 24" width={16} height={16} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
    </svg>
  );
}
function IconCheck() {
  return (
    <svg viewBox="0 0 24 24" width={16} height={16} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="m20 6-11 11-5-5" />
    </svg>
  );
}

export function SprintPage({ jiraReady }: Props) {
  const toast = useToast();
  const [candidates, setCandidates] = useState<TaskOut[] | null>(null);
  const [maxSprint, setMaxSprint] = useState<number | null>(null);
  const [designers, setDesigners] = useState<AssignablePerson[]>([]);
  const [testers, setTesters] = useState<AssignablePerson[]>([]);

  const [sprint, setSprint] = useState<SprintOut | null>(null);
  const [allocated, setAllocated] = useState<TaskOut[] | null>(null);
  const [overflow, setOverflow] = useState<TaskOut[]>([]);
  const [ownerStats, setOwnerStats] = useState<OwnerStat[]>([]);

  const [diagnostics, setDiagnostics] = useState<Record<string, unknown> | null>(null);

  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [loadingSprint, setLoadingSprint] = useState(false);
  const [approving, setApproving] = useState(false);
  const [downloadingC, setDownloadingC] = useState(false);
  const [downloadingS, setDownloadingS] = useState(false);

  useEffect(() => {
    getDefaultConfig().then((cfg) => {
      const entries = Object.entries(cfg.team);
      setDesigners(
        entries
          .filter(([, m]) => m.role.startsWith("designer"))
          .map(([id, m]) => ({ id, name: m.file_name }))
          .sort((a, b) => a.name.localeCompare(b.name)),
      );
      setTesters(
        entries
          .filter(([, m]) => m.role.startsWith("tester") || m.role === "qa")
          .map(([id, m]) => ({ id, name: m.file_name }))
          .sort((a, b) => a.name.localeCompare(b.name)),
      );
    }).catch(() => {/* конфиг недоступен — просто не показываем дропдауны */});
  }, []);

  // Фильтры таблицы
  const [filterOwner, setFilterOwner] = useState("");
  const [filterBucket, setFilterBucket] = useState("");

  // Редактор полей Jira
  const [editingTask, setEditingTask] = useState<TaskOut | null>(null);

  // Режим редактирования состава
  const [editing, setEditing] = useState(false);

  const handleLoadCandidates = async () => {
    setLoadingCandidates(true);
    resetSprint();
    try {
      const r = await fetchCandidates();
      setCandidates(r.candidates);
      setMaxSprint(r.max_sprint_num);
      setDiagnostics(r.diagnostics);
      toast.success(`Загружено кандидатов: ${r.candidates.length}`);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setLoadingCandidates(false);
    }
  };

  const handleBuildSprint = async () => {
    if (!candidates) return;
    setLoadingSprint(true);
    resetSprint();
    try {
      const r = await buildAndSaveSprint(candidates);
      setSprint(r.sprint);
      setAllocated(r.allocated);
      setOverflow(r.overflow);
      setOwnerStats(r.owner_stats);
      setDiagnostics(r.diagnostics);
      toast.success(`Sprint ${r.sprint.sprint_num} сформирован и сохранён`);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setLoadingSprint(false);
    }
  };

  const handleApprove = async () => {
    if (!sprint) return;
    const ok = window.confirm(
      `Утвердить Sprint ${sprint.sprint_num}?\n\n` +
      `В Jira уже должен существовать Sprint ${sprint.sprint_num}.`
    );
    if (!ok) return;
    setApproving(true);
    try {
      const updated = await approveSprint(sprint.id);
      setSprint(updated);
      toast.success(`Sprint ${updated.sprint_num} утверждён`);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setApproving(false);
    }
  };

  const handleDownloadCandidates = async () => {
    if (!candidates) return;
    setDownloadingC(true);
    try {
      const allocatedSet = allocated
        ? allocated
            .filter((t) => !t.is_pseudo)
            .map((t) => `${t.key}|${t.role}|${t.bucket}`)
        : undefined;
      await downloadCandidatesXlsx({
        candidates,
        max_sprint_num: maxSprint,
        allocated_set: allocatedSet,
      });
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setDownloadingC(false);
    }
  };

  const handleDownloadSprint = async () => {
    if (!allocated) return;
    setDownloadingS(true);
    try {
      await downloadSprintXlsx({
        allocated,
        owner_stats: ownerStats,
        max_sprint_num: maxSprint,
      });
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setDownloadingS(false);
    }
  };

  const handleSaveComposer = async (newTasks: TaskOut[]) => {
    if (!sprint) return;
    try {
      const updated = await setSprintTasks(sprint.id, newTasks);
      // Обновляем все локальные состояния новыми данными
      setSprint(updated);
      setAllocated(updated.tasks);
      setOwnerStats(updated.owner_stats);
      setEditing(false);
      toast.success("Состав спринта обновлён");
    } catch (e) {
      toast.error(extractError(e));
    }
  };

  const handlePatchCandidate = (key: string, patch: Partial<TaskOut>) => {
    setCandidates((prev) =>
      prev ? prev.map((t) => (t.key === key ? { ...t, ...patch } : t)) : prev,
    );
  };

  const resetSprint = () => {
    setSprint(null);
    setAllocated(null);
    setOverflow([]);
    setOwnerStats([]);
    setEditing(false);
    setFilterOwner("");
    setFilterBucket("");
  };

  // Применяет обновление полей Jira к локальным спискам задач
  const handleJiraSaved = (
    key: string,
    update: IssueFieldsUpdate,
    devName: string | null,
  ) => {
    const patch = (t: TaskOut): TaskOut => {
      if (t.key !== key) return t;
      return {
        ...t,
        hours_analyst:   update.hours_analyst   ?? t.hours_analyst,
        hours_tester:    update.hours_tester    ?? t.hours_tester,
        hours_developer: update.hours_developer ?? t.hours_developer,
        hours_designer:  update.hours_designer  ?? t.hours_designer,
        developer_name:  devName ?? t.developer_name,
        hours_is_default:
          update.hours_analyst != null ||
          update.hours_tester != null ||
          update.hours_developer != null ||
          update.hours_designer != null
            ? false
            : t.hours_is_default,
      };
    };
    if (candidates) setCandidates(candidates.map(patch));
    if (allocated)  setAllocated(allocated.map(patch));
    setOverflow(overflow.map(patch));
  };

  // Опции для дропдаунов фильтра (из объединения allocated + overflow)
  const allTasks = useMemo(
    () => [...(allocated ?? []), ...overflow],
    [allocated, overflow],
  );
  const ownerOptions = useMemo(
    () => Array.from(new Set(allTasks.map((t) => t.owner_file_name))).sort(),
    [allTasks],
  );
  const bucketOptions = useMemo(
    () => Array.from(new Set(allTasks.map((t) => t.bucket))).sort(),
    [allTasks],
  );

  const applyFilters = (tasks: TaskOut[]) =>
    tasks.filter(
      (t) =>
        (!filterOwner || t.owner_file_name === filterOwner) &&
        (!filterBucket || t.bucket === filterBucket),
    );

  const candidatesCount = candidates?.length ?? 0;
  const formalCount = candidates?.filter((c) => c.formal_only).length ?? 0;

  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
      {!editing && (
        <div className="flex flex-wrap items-center gap-2 mb-4 rounded-xl border border-gray-200 bg-white shadow-sm p-2.5">
          <button
            onClick={handleLoadCandidates}
            disabled={loadingCandidates || !jiraReady}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed shadow-sm transition"
          >
            <IconRefresh />
            {loadingCandidates ? "Загружаю…" : candidates ? "Обновить кандидатов" : "Загрузить кандидатов"}
          </button>

          <button
            onClick={handleDownloadCandidates}
            disabled={!candidates || downloadingC}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed shadow-sm transition"
          >
            <IconDownload />
            {downloadingC ? "Скачиваю…" : "Скачать кандидатов"}
          </button>

          <div className="w-px self-stretch bg-gray-200 mx-1" />

          <button
            onClick={handleBuildSprint}
            disabled={!candidates || loadingSprint}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-300 shadow-sm transition"
          >
            <IconBolt />
            {loadingSprint ? "Формирую и сохраняю…" : "Сформировать спринт"}
          </button>

          <div className="flex-1" />

          {sprint && sprint.status === "draft" && allocated && (
            <button
              onClick={() => setEditing(true)}
              title="Изменить состав вручную"
              className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium border border-amber-300 text-amber-700 bg-amber-50 hover:bg-amber-100 shadow-sm transition"
            >
              <IconEdit />
              Редактировать состав
            </button>
          )}

          <button
            onClick={handleDownloadSprint}
            disabled={!allocated || downloadingS}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-sm font-medium border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed shadow-sm transition"
          >
            <IconDownload />
            {downloadingS ? "Скачиваю…" : "Скачать спринт"}
          </button>

          {sprint && sprint.status === "draft" && (
            <button
              onClick={handleApprove}
              disabled={approving}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold text-white bg-violet-600 hover:bg-violet-700 disabled:bg-gray-300 shadow-sm transition"
            >
              <IconCheck />
              {approving ? "Утверждаю…" : "Утвердить"}
            </button>
          )}
        </div>
      )}

      {!candidates && !loadingCandidates && (
        <div className="text-center text-gray-500 mt-20">
          Нажмите «Загрузить кандидатов», чтобы подтянуть задачи из Jira.
        </div>
      )}

      {candidates && (
        <>
          <div className="text-sm text-gray-600 mb-3 flex flex-wrap items-center gap-4">
            {maxSprint !== null && (
              <span>Макс. в Jira: <b>SHN Sprint {maxSprint}</b></span>
            )}
            <span>
              Кандидатов: <b>{candidatesCount}</b>
              {formalCount > 0 && (
                <span className="text-gray-400"> (формальных: {formalCount})</span>
              )}
            </span>
            {sprint && <SprintStatusBadge sprint={sprint} />}
          </div>

          {diagnostics && <DiagnosticsPanel diagnostics={diagnostics} />}

          {editing && allocated && candidates ? (
            <SprintComposer
              candidates={candidates}
              sprintTasks={allocated}
              ownerStats={ownerStats}
              onSave={handleSaveComposer}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <>
              {ownerStats.length > 0 && <OwnerStats stats={ownerStats} />}

              {/* Фильтры — только когда спринт сформирован */}
              {allocated && sprint && (ownerOptions.length > 1 || bucketOptions.length > 1) && (
                <div className="flex flex-wrap items-center gap-3 mb-3">
                  <span className="text-sm text-gray-500">Фильтр:</span>
                  <select
                    value={filterOwner}
                    onChange={(e) => setFilterOwner(e.target.value)}
                    className="text-sm border rounded px-2 py-1 bg-white"
                  >
                    <option value="">Все исполнители</option>
                    {ownerOptions.map((o) => (
                      <option key={o} value={o}>{o}</option>
                    ))}
                  </select>
                  <select
                    value={filterBucket}
                    onChange={(e) => setFilterBucket(e.target.value)}
                    className="text-sm border rounded px-2 py-1 bg-white"
                  >
                    <option value="">Все фазы</option>
                    {bucketOptions.map((b) => (
                      <option key={b} value={b}>{b}</option>
                    ))}
                  </select>
                  {(filterOwner || filterBucket) && (
                    <button
                      onClick={() => { setFilterOwner(""); setFilterBucket(""); }}
                      className="text-sm text-blue-600 hover:underline"
                    >
                      Сбросить
                    </button>
                  )}
                </div>
              )}

              {allocated && sprint ? (
                <>
                  <h2 className="font-semibold text-gray-700 mb-2">
                    В спринт ({applyFilters(allocated).length}
                    {filterOwner || filterBucket ? ` из ${allocated.length}` : " задач"})
                  </h2>
                  <SprintTable
                    tasks={applyFilters(allocated)}
                    onEditTask={setEditingTask}
                  />
                  {overflow.length > 0 && (
                    <>
                      <h2 className="font-semibold text-gray-700 mt-6 mb-2">
                        Не влезло ({applyFilters(overflow).length}
                        {filterOwner || filterBucket ? ` из ${overflow.length}` : ""})
                      </h2>
                      <SprintTable
                        tasks={applyFilters(overflow)}
                        isOverflow
                        onEditTask={setEditingTask}
                      />
                    </>
                  )}
                </>
              ) : (
                <>
                  <h2 className="font-semibold text-gray-700 mb-2">
                    Кандидаты ({candidatesCount})
                  </h2>
                  <SprintTable
                    tasks={candidates}
                    onEditTask={setEditingTask}
                    designers={designers.length > 0 ? designers : undefined}
                    testers={testers.length > 0 ? testers : undefined}
                    onPatchTask={handlePatchCandidate}
                  />
                </>
              )}
            </>
          )}
        </>
      )}

      {editingTask && (
        <JiraFieldEditor
          task={editingTask}
          onClose={() => setEditingTask(null)}
          onSaved={handleJiraSaved}
        />
      )}

    </div>
  );
}

function SprintStatusBadge({ sprint }: { sprint: SprintOut }) {
  const isApproved = sprint.status === "approved";
  return (
    <span
      className={`px-2 py-1 rounded text-xs font-semibold ${
        isApproved
          ? "bg-green-100 text-green-800"
          : "bg-yellow-100 text-yellow-800"
      }`}
    >
      Sprint {sprint.sprint_num} · {isApproved ? "approved" : "draft"}
    </span>
  );
}