import { useState } from "react";
import {
  approveSprint,
  buildAndSaveSprint,
  downloadCandidatesXlsx,
  downloadSprintXlsx,
  fetchCandidates,
  setSprintTasks,
} from "../api/client";
import { OwnerStats } from "../components/OwnerStats";
import { SprintComposer } from "../components/SprintComposer";
import { SprintTable } from "../components/SprintTable";
import type { OwnerStat, SprintOut, TaskOut } from "../types/api";

interface Props {
  jiraReady: boolean;
}

export function SprintPage({ jiraReady }: Props) {
  const [candidates, setCandidates] = useState<TaskOut[] | null>(null);
  const [maxSprint, setMaxSprint] = useState<number | null>(null);

  const [sprint, setSprint] = useState<SprintOut | null>(null);
  const [allocated, setAllocated] = useState<TaskOut[] | null>(null);
  const [overflow, setOverflow] = useState<TaskOut[]>([]);
  const [ownerStats, setOwnerStats] = useState<OwnerStat[]>([]);

  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [loadingSprint, setLoadingSprint] = useState(false);
  const [approving, setApproving] = useState(false);
  const [downloadingC, setDownloadingC] = useState(false);
  const [downloadingS, setDownloadingS] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Режим редактирования состава
  const [editing, setEditing] = useState(false);

  const handleLoadCandidates = async () => {
    setLoadingCandidates(true);
    setError(null);
    resetSprint();
    try {
      const r = await fetchCandidates();
      setCandidates(r.candidates);
      setMaxSprint(r.max_sprint_num);
    } catch (e) {
      setError(extractError(e));
    } finally {
      setLoadingCandidates(false);
    }
  };

  const handleBuildSprint = async () => {
    if (!candidates) return;
    setLoadingSprint(true);
    setError(null);
    resetSprint();
    try {
      const r = await buildAndSaveSprint(candidates);
      setSprint(r.sprint);
      setAllocated(r.allocated);
      setOverflow(r.overflow);
      setOwnerStats(r.owner_stats);
    } catch (e) {
      setError(extractError(e));
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
    setError(null);
    try {
      const updated = await approveSprint(sprint.id);
      setSprint(updated);
    } catch (e) {
      setError(extractError(e));
    } finally {
      setApproving(false);
    }
  };

  const handleDownloadCandidates = async () => {
    if (!candidates) return;
    setDownloadingC(true);
    setError(null);
    try {
      await downloadCandidatesXlsx({ candidates, max_sprint_num: maxSprint });
    } catch (e) {
      setError(extractError(e));
    } finally {
      setDownloadingC(false);
    }
  };

  const handleDownloadSprint = async () => {
    if (!allocated) return;
    setDownloadingS(true);
    setError(null);
    try {
      await downloadSprintXlsx({
        allocated,
        owner_stats: ownerStats,
        max_sprint_num: maxSprint,
      });
    } catch (e) {
      setError(extractError(e));
    } finally {
      setDownloadingS(false);
    }
  };

  const handleSaveComposer = async (newTasks: TaskOut[]) => {
    if (!sprint) return;
    const updated = await setSprintTasks(sprint.id, newTasks);
    // Обновляем все локальные состояния новыми данными
    setSprint(updated);
    setAllocated(updated.tasks);
    setOwnerStats(updated.owner_stats);
    setEditing(false);
  };

  const resetSprint = () => {
    setSprint(null);
    setAllocated(null);
    setOverflow([]);
    setOwnerStats([]);
    setEditing(false);
  };

  const candidatesCount = candidates?.length ?? 0;
  const formalCount = candidates?.filter((c) => c.formal_only).length ?? 0;

  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
      {!editing && (
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <button
            onClick={handleLoadCandidates}
            disabled={loadingCandidates || !jiraReady}
            className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 text-white font-semibold px-4 py-2 rounded-lg transition"
          >
            {loadingCandidates ? "Загружаю…" : candidates ? "Обновить кандидатов" : "Загрузить кандидатов"}
          </button>

          <button
            onClick={handleDownloadCandidates}
            disabled={!candidates || downloadingC}
            className="bg-gray-600 hover:bg-gray-700 disabled:bg-gray-300 text-white font-semibold px-4 py-2 rounded-lg transition"
          >
            {downloadingC ? "Скачиваю…" : "Скачать кандидатов"}
          </button>

          <div className="flex-1" />

          <button
            onClick={handleBuildSprint}
            disabled={!candidates || loadingSprint}
            className="bg-green-600 hover:bg-green-700 disabled:bg-gray-300 text-white font-semibold px-4 py-2 rounded-lg transition"
          >
            {loadingSprint ? "Формирую и сохраняю…" : "Сформировать спринт"}
          </button>

          {sprint && sprint.status === "draft" && allocated && (
            <button
              onClick={() => setEditing(true)}
              className="bg-yellow-500 hover:bg-yellow-600 text-white font-semibold px-4 py-2 rounded-lg transition"
              title="Изменить состав вручную"
            >
              Редактировать состав
            </button>
          )}

          <button
            onClick={handleDownloadSprint}
            disabled={!allocated || downloadingS}
            className="bg-green-700 hover:bg-green-800 disabled:bg-gray-300 text-white font-semibold px-4 py-2 rounded-lg transition"
          >
            {downloadingS ? "Скачиваю…" : "Скачать спринт"}
          </button>

          {sprint && sprint.status === "draft" && (
            <button
              onClick={handleApprove}
              disabled={approving}
              className="bg-purple-600 hover:bg-purple-700 disabled:bg-gray-300 text-white font-semibold px-4 py-2 rounded-lg transition"
            >
              {approving ? "Утверждаю…" : "Утвердить"}
            </button>
          )}
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-300 text-red-800 rounded-lg p-3 mb-4">
          {error}
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

          {editing && allocated && candidates ? (
            // Режим редактирования состава
            <SprintComposer
              candidates={candidates}
              sprintTasks={allocated}
              ownerStats={ownerStats}
              onSave={handleSaveComposer}
              onCancel={() => setEditing(false)}
            />
          ) : (
            // Обычный режим
            <>
              {ownerStats.length > 0 && <OwnerStats stats={ownerStats} />}
              {allocated && sprint ? (
                <>
                  <h2 className="font-semibold text-gray-700 mb-2">
                    В спринт ({allocated.length} задач)
                  </h2>
                  <SprintTable tasks={allocated} />
                  {overflow.length > 0 && (
                    <>
                      <h2 className="font-semibold text-gray-700 mt-6 mb-2">
                        Не влезло ({overflow.length})
                      </h2>
                      <SprintTable tasks={overflow} />
                    </>
                  )}
                </>
              ) : (
                <>
                  <h2 className="font-semibold text-gray-700 mb-2">
                    Кандидаты ({candidatesCount})
                  </h2>
                  <SprintTable tasks={candidates} />
                </>
              )}
            </>
          )}
        </>
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

function extractError(e: unknown): string {
  if (e && typeof e === "object" && "response" in e) {
    const r = (e as { response?: { data?: { detail?: string } } }).response;
    if (r?.data?.detail) return r.data.detail;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}
