import axios from "axios";
import { triggerDownload } from "../lib/download";
import type {
  BuildAndSaveResponse, ClosedTaskData, ConfigOut, ConfigUpdate, EmployeeVacation,
  GanttSnapshotDetail, GanttSnapshotSummary, LoginResponse, OwnerStat, RootTaskOut,
  SprintBuildResponse, SprintOut, SprintSummary, TaskDependency, TaskOut, UserOut,
} from "../types/api";

const envUrl = import.meta.env.VITE_API_URL;
const baseURL =
  envUrl === undefined ? "http://localhost:8000" : envUrl;

export const api = axios.create({ baseURL });

const TOKEN_KEY = "sb_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

api.interceptors.request.use((cfg) => {
  const t = getToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err?.response?.status === 401) {
      setToken(null);
    }
    return Promise.reject(err);
  },
);

// -------------------- Auth --------------------

export async function login(email: string, password: string): Promise<LoginResponse> {
  const r = await api.post("/api/auth/login", { email, password });
  return r.data;
}

export async function getMe(): Promise<UserOut> {
  const r = await api.get("/api/auth/me");
  return r.data;
}

// -------------------- Health / Jira --------------------

export async function checkJira(): Promise<{ display_name: string; email: string }> {
  const r = await api.get("/api/jira/check");
  return r.data;
}

// -------------------- Sprint build --------------------

export async function fetchCandidates(): Promise<{
  candidates: TaskOut[];
  diagnostics: Record<string, unknown>;
  max_sprint_num: number | null;
}> {
  const r = await api.post("/api/sprint/candidates");
  return r.data;
}

export async function buildAndSaveSprint(candidates?: TaskOut[]): Promise<BuildAndSaveResponse> {
  const body = candidates ? { candidates } : {};
  const r = await api.post("/api/sprint/build-and-save", body);
  return r.data;
}

export async function buildSprint(candidates?: TaskOut[]): Promise<SprintBuildResponse> {
  const body = candidates ? { candidates } : {};
  const r = await api.post("/api/sprint/build", body);
  return r.data;
}

// -------------------- Config --------------------

export async function getDefaultConfig(): Promise<ConfigOut> {
  const r = await api.get("/api/configs/default");
  return r.data;
}

export async function updateConfig(id: number, body: ConfigUpdate): Promise<ConfigOut> {
  const r = await api.put(`/api/configs/${id}`, body);
  return r.data;
}

// -------------------- Sprint history --------------------

export async function listSprints(): Promise<SprintSummary[]> {
  const r = await api.get("/api/sprints");
  return r.data;
}

export async function getSprint(id: number): Promise<SprintOut> {
  const r = await api.get(`/api/sprints/${id}`);
  return r.data;
}

export async function approveSprint(id: number): Promise<SprintOut> {
  const r = await api.post(`/api/sprints/${id}/approve`);
  return r.data;
}

export async function reopenSprint(id: number): Promise<SprintOut> {
  const r = await api.post(`/api/sprints/${id}/reopen`);
  return r.data;
}

export async function closeSprint(id: number): Promise<SprintOut> {
  const r = await api.post(`/api/sprints/${id}/close`);
  return r.data;
}

export async function deleteSprint(id: number): Promise<void> {
  await api.delete(`/api/sprints/${id}`);
}

export async function fetchEpicForecast(
  key: string,
  startDate: string,
  hoursPerDay: number = 8,
  useHistory: boolean = false,
  sprintId?: number,
): Promise<import("../types/api").EpicForecastResponse> {
  const r = await api.get("/api/epic/forecast", {
    params: {
      key: key || undefined,
      sprint_id: sprintId,
      start_date: startDate,
      hours_per_day: hoursPerDay,
      use_history: useHistory || undefined,
    },
  });
  return r.data;
}

export async function fetchStandup(
  sprintId: number,
  sprintStart: string,
  standupDate: string,
  hoursPerDay: number,
  roles: string[],
): Promise<import("../types/api").StandupExecutor[]> {
  const r = await api.get(`/api/sprints/${sprintId}/standup`, {
    params: {
      sprint_start: sprintStart,
      standup_date: standupDate,
      hours_per_day: hoursPerDay,
      roles: roles.join(","),
    },
  });
  return r.data;
}

export async function submitStandup(payload: {
  standup_date: string;
  updates: {
    key: string;
    owner_file_name: string;
    bucket: string;
    status: string;
    comment: string;
    push_to_jira: boolean;
  }[];
}): Promise<import("../types/api").StandupSubmitResult[]> {
  const r = await api.post("/api/jira/standup/submit", payload);
  return r.data;
}

export async function fetchGantt(
  sprintId: number,
  startDate: string,
  hoursPerDay: number = 8,
): Promise<import("../types/api").GanttItem[]> {
  const r = await api.get(`/api/sprints/${sprintId}/gantt`, {
    params: { start_date: startDate, hours_per_day: hoursPerDay },
  });
  return r.data;
}

// -------------------- Снимки Ганта спринта --------------------

export async function saveGanttSnapshot(
  sprintId: number,
  ganttStart: string,
  hoursPerDay: number,
  ganttItems: import("../types/api").GanttItem[],
  label?: string,
): Promise<GanttSnapshotSummary> {
  const r = await api.post(`/api/sprints/${sprintId}/gantt/snapshots`, {
    gantt_start: ganttStart,
    hours_per_day: hoursPerDay,
    gantt_items: ganttItems,
    label: label || undefined,
  });
  return r.data;
}

export async function listGanttSnapshots(sprintId: number): Promise<GanttSnapshotSummary[]> {
  const r = await api.get(`/api/sprints/${sprintId}/gantt/snapshots`);
  return r.data;
}

export async function getGanttSnapshot(
  sprintId: number, snapshotId: number,
): Promise<GanttSnapshotDetail> {
  const r = await api.get(`/api/sprints/${sprintId}/gantt/snapshots/${snapshotId}`);
  return r.data;
}

export async function deleteGanttSnapshot(sprintId: number, snapshotId: number): Promise<void> {
  await api.delete(`/api/sprints/${sprintId}/gantt/snapshots/${snapshotId}`);
}

// -------------------- Снимки Ганта эпика (прогноз) --------------------
// Тот же механизм, что и снимки Ганта спринта выше, но привязан к epic_key.

export async function saveEpicGanttSnapshot(
  epicKey: string,
  ganttStart: string,
  hoursPerDay: number,
  ganttItems: import("../types/api").GanttItem[],
  label?: string,
): Promise<GanttSnapshotSummary> {
  const r = await api.post(`/api/epic/gantt/snapshots`, {
    gantt_start: ganttStart,
    hours_per_day: hoursPerDay,
    gantt_items: ganttItems,
    label: label || undefined,
  }, { params: { epic_key: epicKey } });
  return r.data;
}

export async function listEpicGanttSnapshots(epicKey: string): Promise<GanttSnapshotSummary[]> {
  const r = await api.get(`/api/epic/gantt/snapshots`, { params: { epic_key: epicKey } });
  return r.data;
}

export async function getEpicGanttSnapshot(
  epicKey: string, snapshotId: number,
): Promise<GanttSnapshotDetail> {
  const r = await api.get(`/api/epic/gantt/snapshots/${snapshotId}`, { params: { epic_key: epicKey } });
  return r.data;
}

export async function deleteEpicGanttSnapshot(epicKey: string, snapshotId: number): Promise<void> {
  await api.delete(`/api/epic/gantt/snapshots/${snapshotId}`, { params: { epic_key: epicKey } });
}

// -------------------- Epic Snapshots --------------------

export async function fetchEpicSnapshots(
  epicKey: string,
): Promise<import("../types/api").EpicForecastSnapshot[]> {
  const r = await api.get("/api/epic/snapshots", { params: { epic_key: epicKey } });
  return r.data;
}

export async function deleteEpicSnapshot(id: number): Promise<void> {
  await api.delete(`/api/epic/snapshots/${id}`);
}

export async function pinEpicSnapshot(
  id: number,
  pinned: boolean,
): Promise<import("../types/api").EpicForecastSnapshot> {
  const r = await api.patch(`/api/epic/snapshots/${id}/pin`, null, { params: { pinned } });
  return r.data;
}

// -------------------- Epic Dependencies --------------------

export async function fetchSprintDependencies(sprintId: number): Promise<TaskDependency[]> {
  const r = await api.get(`/api/sprints/${sprintId}/dependencies`);
  return r.data;
}

export async function fetchEpicDependencies(epicKey: string): Promise<TaskDependency[]> {
  const r = await api.get("/api/epic/dependencies", { params: { epic_key: epicKey } });
  return r.data;
}

export async function addEpicDependency(epicKey: string, dep: TaskDependency): Promise<TaskDependency[]> {
  const r = await api.post("/api/epic/dependencies", dep, { params: { epic_key: epicKey } });
  return r.data;
}

export async function removeEpicDependency(epicKey: string, dep: TaskDependency): Promise<void> {
  await api.delete("/api/epic/dependencies", { data: dep, params: { epic_key: epicKey } });
}

// -------------------- Стартовые задачи (root tasks) --------------------

export async function fetchRootTasks(epicKey: string): Promise<RootTaskOut[]> {
  const r = await api.get("/api/epic/root-tasks", { params: { epic_key: epicKey } });
  return r.data;
}

export async function setRootTask(
  epicKey: string, ownerId: string, taskKey: string,
): Promise<RootTaskOut[]> {
  const r = await api.post(
    "/api/epic/root-tasks",
    { owner_id: ownerId, task_key: taskKey },
    { params: { epic_key: epicKey } },
  );
  return r.data;
}

export async function removeRootTask(epicKey: string, ownerId: string): Promise<void> {
  await api.delete("/api/epic/root-tasks", { params: { epic_key: epicKey, owner_id: ownerId } });
}

// -------------------- Vacations --------------------

export async function fetchVacations(): Promise<EmployeeVacation[]> {
  const r = await api.get("/api/configs/vacations");
  return r.data;
}

export async function addVacation(
  data: Omit<EmployeeVacation, "id">
): Promise<EmployeeVacation> {
  const r = await api.post("/api/configs/vacations", data);
  return r.data;
}

export async function deleteVacation(id: number): Promise<void> {
  await api.delete(`/api/configs/vacations/${id}`);
}

export async function setSprintTasks(id: number, tasks: TaskOut[]): Promise<SprintOut> {
  const r = await api.put(`/api/sprints/${id}/tasks`, { tasks });
  return r.data;
}

// -------------------- xlsx --------------------

interface SprintExportPayload {
  allocated: TaskOut[];
  owner_stats: OwnerStat[];
  max_sprint_num: number | null;
  closed_tasks?: (ClosedTaskData | null)[];
  terminal_statuses?: string[];
  // Фаза 2.10
  intrusions?: unknown[];
}

interface CandidatesExportPayload {
  candidates: TaskOut[];
  max_sprint_num: number | null;
  allocated_set?: string[];  // "key|role|bucket" для аллоцированных задач
}

async function downloadBlob(url: string, payload: object, fallbackName: string) {
  const r = await api.post(url, payload, { responseType: "blob" });

  const cd: string = r.headers["content-disposition"] || "";
  const match = cd.match(/filename\*=UTF-8''([^;]+)/i);
  const filename = match ? decodeURIComponent(match[1]) : fallbackName;

  triggerDownload(r.data as Blob, filename);
}

export async function downloadSprintXlsx(payload: SprintExportPayload) {
  await downloadBlob("/api/sprint/export", payload, "sprint.xlsx");
}

export async function downloadCandidatesXlsx(payload: CandidatesExportPayload) {
  await downloadBlob("/api/candidates/export", payload, "candidates.xlsx");
}

export async function downloadEpicForecastXlsx(epicKey: string, ganttItems: unknown[]) {
  await downloadBlob("/api/epic/forecast/export", { epic_key: epicKey, gantt_items: ganttItems }, `forecast_${epicKey}.xlsx`);
}
