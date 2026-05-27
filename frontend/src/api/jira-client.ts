// API-клиент для поиска людей в Jira.

import { api } from "./client";
import type { JiraUserSearchResult } from "../types/intrusions";

export async function searchJiraUsers(q: string): Promise<JiraUserSearchResult[]> {
  const r = await api.get("/api/jira/users/search", { params: { q } });
  return r.data;
}

export interface IssueFieldsUpdate {
  hours_analyst?: number | null;
  hours_tester?: number | null;
  hours_developer?: number | null;
  hours_designer?: number | null;
  developer_account_id?: string | null;
}

export async function updateJiraIssueFields(
  key: string,
  update: IssueFieldsUpdate,
): Promise<void> {
  await api.patch(`/api/jira/issues/${key}/fields`, update);
}
