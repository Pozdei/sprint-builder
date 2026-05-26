// Админский API-клиент.

import axios from "axios";
import { getToken } from "./client";
import type {
  AdminConfigSummary,
  AdminSprintSummary,
  AdminTeamMember,
  UserCreateRequest,
  UserUpdateRequest,
} from "../types/admin";
import type { UserOut } from "../types/api";

// baseURL: пустая строка = относительные пути (Docker), undefined = fallback на :8000 (dev).
const envUrl = import.meta.env.VITE_API_URL;
const baseURL =
  envUrl === undefined ? "http://localhost:8000" : envUrl;

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

// ---------- Обзор ----------

export async function adminListConfigs(): Promise<AdminConfigSummary[]> {
  const r = await axios.get(`${baseURL}/api/admin/configs`, { headers: authHeaders() });
  return r.data;
}

export async function adminListSprints(): Promise<AdminSprintSummary[]> {
  const r = await axios.get(`${baseURL}/api/admin/sprints`, { headers: authHeaders() });
  return r.data;
}

// ---------- Пользователи ----------

export async function adminListUsers(): Promise<UserOut[]> {
  const r = await axios.get(`${baseURL}/api/admin/users`, { headers: authHeaders() });
  return r.data;
}

export async function adminCreateUser(body: UserCreateRequest): Promise<UserOut> {
  const r = await axios.post(`${baseURL}/api/admin/users`, body, { headers: authHeaders() });
  return r.data;
}

export async function adminUpdateUser(id: number, body: UserUpdateRequest): Promise<UserOut> {
  const r = await axios.patch(`${baseURL}/api/admin/users/${id}`, body, { headers: authHeaders() });
  return r.data;
}

export async function adminResetPassword(id: number, newPassword: string): Promise<void> {
  await axios.post(
    `${baseURL}/api/admin/users/${id}/reset-password`,
    { new_password: newPassword },
    { headers: authHeaders() },
  );
}

export async function adminDeleteUser(id: number): Promise<void> {
  await axios.delete(`${baseURL}/api/admin/users/${id}`, { headers: authHeaders() });
}

// ---------- Оклады ----------

export async function adminGetConfigTeam(configId: number): Promise<AdminTeamMember[]> {
  const r = await axios.get(`${baseURL}/api/admin/configs/${configId}/team`, { headers: authHeaders() });
  return r.data;
}

export async function adminUpdateSalaries(configId: number, salaries: Record<string, number>): Promise<void> {
  await axios.patch(
    `${baseURL}/api/admin/configs/${configId}/salaries`,
    { salaries },
    { headers: authHeaders() },
  );
}

// ---------- Передача конфига ----------

export async function adminTransferConfig(
  configId: number,
  newOwnerUserId: number,
): Promise<AdminConfigSummary> {
  const r = await axios.post(
    `${baseURL}/api/admin/configs/${configId}/transfer`,
    { new_owner_user_id: newOwnerUserId },
    { headers: authHeaders() },
  );
  return r.data;
}
