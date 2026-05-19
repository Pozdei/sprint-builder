// Методы для управления конфигами (фаза 2.8).

import axios from "axios";
import { getToken } from "./client";
import type { ConfigOut } from "../types/api";
import type { ConfigCreateRequest, ConfigSummary } from "../types/configs";

// baseURL: пустая строка = относительные пути (Docker), undefined = fallback на :8000 (dev).
const envUrl = import.meta.env.VITE_API_URL;
const baseURL =
  envUrl === undefined ? "http://localhost:8000" : envUrl;

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export async function listMyConfigs(): Promise<ConfigSummary[]> {
  const r = await axios.get(`${baseURL}/api/configs`, { headers: authHeaders() });
  return r.data;
}

export async function createConfig(body: ConfigCreateRequest): Promise<ConfigOut> {
  const r = await axios.post(`${baseURL}/api/configs`, body, { headers: authHeaders() });
  return r.data;
}

export async function activateConfig(id: number): Promise<ConfigOut> {
  const r = await axios.post(`${baseURL}/api/configs/${id}/activate`, null,
                              { headers: authHeaders() });
  return r.data;
}

export async function deleteConfigById(id: number): Promise<void> {
  await axios.delete(`${baseURL}/api/configs/${id}`, { headers: authHeaders() });
}
