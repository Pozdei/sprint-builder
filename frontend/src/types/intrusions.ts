// Типы для фазы 2.10.

export interface IntrusionRecord {
  key: string;
  summary: string;
  status_name: string;
  is_done: boolean;
  owner_id: string;
  owner_file_name: string;
  owner_jira_name: string;
  role: string;
  bucket: string;
  hours: number;
  url: string | null;
}

export interface JiraUserSearchResult {
  account_id: string;
  display_name: string;
  email: string | null;
  avatar_url: string | null;
}
