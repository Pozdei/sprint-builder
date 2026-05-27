// Админский API-клиент.

import { api } from "./client";
import type {
  AdminConfigSummary,
  AdminSprintSummary,
  AdminTeamMember,
  UserCreateRequest,
  UserUpdateRequest,
} from "../types/admin";
import type { UserOut } from "../types/api";

// ---------- Обзор ----------

export async function adminListConfigs(): Promise<AdminConfigSummary[]> {
  const r = await api.get("/api/admin/configs");
  return r.data;
}

export async function adminListSprints(): Promise<AdminSprintSummary[]> {
  const r = await api.get("/api/admin/sprints");
  return r.data;
}

// ---------- Пользователи ----------

export async function adminListUsers(): Promise<UserOut[]> {
  const r = await api.get("/api/admin/users");
  return r.data;
}

export async function adminCreateUser(body: UserCreateRequest): Promise<UserOut> {
  const r = await api.post("/api/admin/users", body);
  return r.data;
}

export async function adminUpdateUser(id: number, body: UserUpdateRequest): Promise<UserOut> {
  const r = await api.patch(`/api/admin/users/${id}`, body);
  return r.data;
}

export async function adminResetPassword(id: number, newPassword: string): Promise<void> {
  await api.post(`/api/admin/users/${id}/reset-password`, { new_password: newPassword });
}

export async function adminDeleteUser(id: number): Promise<void> {
  await api.delete(`/api/admin/users/${id}`);
}

// ---------- Оклады (глобальные) ----------

export async function adminGetAllSalaries(): Promise<AdminTeamMember[]> {
  const r = await api.get("/api/admin/salaries");
  return r.data;
}

export async function adminUpdateAllSalaries(salaries: Record<string, number>): Promise<void> {
  await api.patch("/api/admin/salaries", { salaries });
}

// ---------- Передача конфига ----------

export async function adminTransferConfig(
  configId: number,
  newOwnerUserId: number,
): Promise<AdminConfigSummary> {
  const r = await api.post(`/api/admin/configs/${configId}/transfer`, {
    new_owner_user_id: newOwnerUserId,
  });
  return r.data;
}
