import axios from "axios";
import type {
  ConfigOut, ConfigUpdate, OwnerStat, SprintBuildResponse, TaskOut
} from "../types/api";

// Базовый URL берётся из переменной окружения VITE_API_URL.
const baseURL = import.meta.env.VITE_API_URL || "http://localhost:8000";
const api = axios.create({ baseURL });

export async function checkJira(): Promise<{ display_name: string; email: string }> {
  const r = await api.get("/api/jira/check");
  return r.data;
}

export async function fetchCandidates(): Promise<{
  candidates: TaskOut[];
  diagnostics: Record<string, unknown>;
  max_sprint_num: number | null;
}> {
  const r = await api.post("/api/sprint/candidates");
  return r.data;
}

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

// ---------- Скачивание xlsx ----------

interface SprintExportPayload {
  allocated: TaskOut[];
  owner_stats: OwnerStat[];
  max_sprint_num: number | null;
}

interface CandidatesExportPayload {
  candidates: TaskOut[];
  max_sprint_num: number | null;
}

/** Универсальная функция: POST с blob-ответом → диалог "Сохранить". */
async function downloadBlob(url: string, payload: object, fallbackName: string) {
  const r = await api.post(url, payload, { responseType: "blob" });

  // Имя файла бэк передаёт в Content-Disposition (filename*=UTF-8''...)
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
