import axios from "axios";
import type {
  BuildAndSaveResponse, ClosedTaskData, ConfigOut, ConfigUpdate, LoginResponse,
  OwnerStat, SprintBuildResponse, SprintOut, SprintSummary, TaskOut, UserOut,
} from "../types/api";

// baseURL:
// - В Docker-проде VITE_API_URL пустой → axios ходит на относительные пути
//   (browser сам подставит текущий origin, и Caddy прокинет /api/* на backend).
// - В локальном dev (npm run dev) VITE_API_URL не задан → fallback на :8000.
//
// Тонкость: import.meta.env.VITE_API_URL может быть undefined (не задано) или
// пустой строкой (задано как ""). Различаем явно — пустая строка значит
// "относительные пути".
const envUrl = import.meta.env.VITE_API_URL;
const baseURL =
  envUrl === undefined ? "http://localhost:8000" : envUrl;

const api = axios.create({ baseURL });

// -------------------- Auth helpers --------------------

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

// -------------------- Auth API --------------------

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

// -------------------- Скачивание xlsx --------------------

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
