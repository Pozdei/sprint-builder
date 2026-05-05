// Типы зеркалят Pydantic-схемы из backend/app/api/routes.py.
// Если меняешь там — меняй здесь.

export interface TaskOut {
  key: string;
  url: string;
  summary: string;
  status_name: string;
  bucket: string;
  owner_id: string;
  owner_file_name: string;
  hours: number;
  board: string;
  sprint_num: number | null;
  sprint_name: string | null;
  formal_only: boolean;
  priority: number | null;
  partial_from: number | null;
  hours_analyst: number | null;
  hours_tester: number | null;
  hours_developer: number | null;
  hours_original: number | null;
}

export interface OwnerStat {
  owner_id: string;
  file_name: string;
  used_hours: number;
  budget: number;
}

export interface SprintBuildResponse {
  allocated: TaskOut[];
  overflow: TaskOut[];
  candidates: TaskOut[];
  owner_stats: OwnerStat[];
  diagnostics: Record<string, unknown>;
  max_sprint_num: number | null;
}

// ---------- Config ----------

export interface TeamMember {
  jira_name: string;
  file_name: string;
}

export interface ConfigOut {
  id: number;
  name: string;
  is_default: boolean;
  project_key: string;
  sprint_field: string;
  responsible_field: string;
  hours_per_person: number;
  default_task_hours: number;
  team: Record<string, TeamMember>;        // accountId -> {jira_name, file_name}
  boards: Record<string, number>;           // board name -> jira id
  extra_components: string[];
  status_bucket: Record<string, string>;    // jira status -> bucket
  status_priority: Record<string, number>;  // jira status -> priority number
  bucket_hours_field: Record<string, string>;  // bucket -> customfield_id
  role_hours_fields: Record<string, string>;   // role -> customfield_id
  strict_assignee_buckets: string[];
}

// Тип для PUT — все поля опциональны
export type ConfigUpdate = Partial<Omit<ConfigOut, "id" | "is_default">>;
