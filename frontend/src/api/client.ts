import axios from "axios";
import type {
  BuildAndSaveResponse, ClosedTaskData, ConfigOut, ConfigUpdate, OwnerStat,
  SprintBuildResponse, SprintOut, SprintSummary, TaskOut,
} from "../types/api";

const baseURL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const api = axios.create({ baseURL });

// ---------- Health / Jira ----------

export async function checkJira(): Promise<{ display_name: string; email: string }> {
  const r = await api.get("/api/jira/check");
  return r.data;
}

// ---------- Sprint build ----------

export async function fetchCandidates(): Promise<{
  candidates: TaskOut[];
  diagnostics: Record<string, unknown>;
  max_sprint_num: number | null;
}> {
  const r = await api.post("/api/sprint/candidates");
  return r.data;
}

/** allocate + автосохранение в БД как draft. Атомарно. */
export async function buildAndSaveSprint(candidates?: TaskOut[]): Promise<BuildAndSaveResponse> {
  const body = candidates ? { candidates } : {};
  const r = await api.post("/api/sprint/build-and-save", body);
  return r.data;
}

/** Чистый allocate без сохранения — для отладки. */
export async function buildSprint(candidates?: TaskOut[]): Promise<SprintBuildResponse> {
  const body = candidates ? { candidates } : {};
  const r = await api.post("/api/sprint/build", body);
  return r.data;
}

// ---------- Config ----------

export async function getDefaultConfig(): Promise<ConfigOut> {
  const r = await api.get("/api/configs/default");
  return r.data;
}

export async function updateConfig(id: number, body: ConfigUpdate): Promise<ConfigOut> {
  const r = await api.put(`/api/configs/${id}`, body);
  return r.data;
}

// ---------- Sprint history ----------

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

export async function closeSprint(id: number): Promise<SprintOut> {
  const r = await api.post(`/api/sprints/${id}/close`);
  return r.data;
}

export async function deleteSprint(id: number): Promise<void> {
  await api.delete(`/api/sprints/${id}`);
}

export async function setSprintTasks(id: number, tasks: TaskOut[]): Promise<SprintOut> {
  const r = await api.put(`/api/sprints/${id}/tasks`, { tasks });
  return r.data;
}

// ---------- Скачивание xlsx ----------

interface SprintExportPayload {
  allocated: TaskOut[];
  owner_stats: OwnerStat[];
  max_sprint_num: number | null;
  closed_tasks?: (ClosedTaskData | null)[];
  terminal_statuses?: string[];
}

interface CandidatesExportPayload {
  candidates: TaskOut[];
  max_sprint_num: number | null;
}

async function downloadBlob(url: string, payload: object, fallbackName: string) {
  const r = await api.post(url, payload, { responseType: "blob" });

  const cd: string = r.headers["content-disposition"] || "";
  const match = cd.match(/filename\*=UTF-8''([^;]+)/i);
  const filename = match ? decodeURIComponent(match[1]) : fallbackName;

  const blobUrl = window.URL.createObjectURL(r.data as Blob);
  const a = document.createElement("a");
  a.href = blobUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(blobUrl);
}

export async function downloadSprintXlsx(payload: SprintExportPayload) {
  await downloadBlob("/api/sprint/export", payload, "sprint.xlsx");
}

export async function downloadCandidatesXlsx(payload: CandidatesExportPayload) {
  await downloadBlob("/api/candidates/export", payload, "candidates.xlsx");
}
