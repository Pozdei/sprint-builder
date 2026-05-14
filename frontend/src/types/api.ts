// Типы зеркалят Pydantic-схемы из backend/app/schemas/

export interface TaskOut {
  key: string;
  url: string;
  summary: string;
  status_name: string;
  bucket: string;
  role: string;
  is_pseudo: boolean;
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

// ---------- Config (фаза 2) ----------

export interface TeamMemberOut {
  id: number;
  jira_name: string;
  file_name: string;
  role: string;  // analyst | designer | designer_lead | developer | developer_lead
}

export interface RoleOut {
  name: string;
  display_name: string;
  enabled: boolean;
  is_lead: boolean;
  sort_order: number;
}

export interface RoleStatusBucketOut {
  role: string;
  jira_status: string;
  bucket: string;
}

export interface RoleStatusDefaultHoursOut {
  role: string;
  jira_status: string;
  hours: number;
}

export interface PseudoTaskOut {
  member_id: number;
  name: string;
  bucket: string;
  hours: number;
  recurring: boolean;
  target_sprint_num: number | null;
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
  leader_hours: number;
  leader_management_enabled: boolean;

  team: Record<string, TeamMemberOut>;
  boards: Record<string, number>;
  extra_components: string[];
  status_priority: Record<string, number>;
  role_hours_fields: Record<string, string>;

  roles: RoleOut[];
  role_status_buckets: RoleStatusBucketOut[];
  role_status_default_hours: RoleStatusDefaultHoursOut[];
  pseudo_tasks: PseudoTaskOut[];
  terminal_statuses: string[];
}

export interface TeamMemberIn {
  jira_name: string;
  file_name: string;
  role: string;
}

export interface ConfigUpdate {
  name?: string;
  project_key?: string;
  sprint_field?: string;
  responsible_field?: string;
  hours_per_person?: number;
  default_task_hours?: number;
  leader_hours?: number;
  leader_management_enabled?: boolean;
  team?: Record<string, TeamMemberIn>;
  boards?: Record<string, number>;
  extra_components?: string[];
  status_priority?: Record<string, number>;
  role_hours_fields?: Record<string, string>;
  roles?: RoleOut[];
  role_status_buckets?: RoleStatusBucketOut[];
  role_status_default_hours?: RoleStatusDefaultHoursOut[];
  pseudo_tasks?: PseudoTaskOut[];
  terminal_statuses?: string[];
}

// ---------- Sprint history ----------

export type SprintStatus = "draft" | "approved" | "closed";

export interface SprintSummary {
  id: number;
  sprint_num: number;
  status: SprintStatus;
  created_at: string;
  approved_at: string | null;
  closed_at: string | null;
  tasks_count: number;
}

export interface ClosedTaskData {
  status_name: string;
  fetched_at: string;
}

export interface SprintOut {
  id: number;
  sprint_num: number;
  status: SprintStatus;
  created_at: string;
  approved_at: string | null;
  closed_at: string | null;
  jira_completed_at: string | null;
  max_sprint_in_jira: number | null;
  config_snapshot: Record<string, unknown>;
  owner_stats: OwnerStat[];
  tasks: TaskOut[];
  closed_tasks: (ClosedTaskData | null)[];
}

export interface BuildAndSaveResponse extends SprintBuildResponse {
  sprint: SprintOut;
}
