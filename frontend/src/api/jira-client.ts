// API-клиент для поиска людей в Jira.

import axios from "axios";
import { getToken } from "./client";
import type { JiraUserSearchResult } from "../types/intrusions";

const envUrl = import.meta.env.VITE_API_URL;
const baseURL =
  envUrl === undefined ? "http://localhost:8000" : envUrl;

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export async function searchJiraUsers(q: string): Promise<JiraUserSearchResult[]> {
  const r = await axios.get(`${baseURL}/api/jira/users/search`, {
    headers: authHeaders(),
    params: { q },
  });
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
  await axios.patch(`${baseURL}/api/jira/issues/${key}/fields`, update, {
    headers: authHeaders(),
  });
}
