// Методы для управления конфигами (фаза 2.8).

import { api } from "./client";
import type { ConfigOut } from "../types/api";
import type { ConfigCreateRequest, ConfigSummary, ConfigTemplate } from "../types/configs";

export async function listMyConfigs(): Promise<ConfigSummary[]> {
  const r = await api.get("/api/configs");
  return r.data;
}

export async function listConfigTemplates(): Promise<ConfigTemplate[]> {
  const r = await api.get("/api/configs/templates");
  return r.data;
}

export async function createConfig(body: ConfigCreateRequest): Promise<ConfigOut> {
  const r = await api.post("/api/configs", body);
  return r.data;
}

export async function activateConfig(id: number): Promise<ConfigOut> {
  const r = await api.post(`/api/configs/${id}/activate`, null);
  return r.data;
}

export async function deleteConfigById(id: number): Promise<void> {
  await api.delete(`/api/configs/${id}`);
}
