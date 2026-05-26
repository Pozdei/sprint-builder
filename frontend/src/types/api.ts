// Типы для API.

export interface TaskOut {
  key: string;
  url: string;
  summary: string;
  status_name: string;
  bucket: string;
  role: string;
  owner_id: string;
  owner_file_name: string;
  hours: number;
  sprint_num: number | null;
  priority: number | null;
  is_pseudo: boolean;
  formal_only?: boolean;
  partial_from?: number;
  // Ожидаемый итог спринта по pipeline (бакет последнего шага или терминальный статус)
  sprint_expected_result?: string | null;
  // Pipeline-поля (round-trip через candidates)
  direction?: string | null;
  labels?: string[];
  responsible_id?: string | null;
  assignee_id?: string | null;
  reporter_id?: string | null;
  hours_analyst?: number | null;
  hours_tester?: number | null;
  hours_developer?: number | null;
  hours_original?: number | null;
  hours_is_default?: boolean;
  overflow_reason?: string | null;
  developer_name?: string | null;
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
  // Фаза 2.10 — список врывов
  intrusions?: unknown[];
}

export interface EpicStats {
  total_issues: number;
  done_issues: number;
  remaining_work_items: number;
  total_planned_hours: number;
  default_hours_count: number;
  total_cost: number;
}

export interface CostBreakdownItem {
  name: string;
  hours: number;
  salary: number;
  cost: number;
}

export interface EpicForecastResponse {
  epic_key: string;
  epic_summary: string;
  gantt_items: GanttItem[];
  completion_date: string | null;
  stats: EpicStats;
  cost_breakdown: CostBreakdownItem[];
  warnings: string[];
}

export interface StandupTask {
  key: string;
  summary: string;
  url: string;
  bucket: string;
  planned_start: string;
  planned_end: string;
  planned_hours: number;
  is_overdue: boolean;
}

export interface StandupExecutor {
  owner_id: string;
  owner_file_name: string;
  role: string;
  tasks: StandupTask[];
}

export interface StandupSubmitResult {
  key: string;
  bucket: string;
  pushed: boolean;
  error?: string | null;
}

export interface GanttItem {
  key: string;
  summary: string;
  bucket: string;
  role: string;
  owner_id: string;
  owner_file_name: string;
  hours: number;
  is_pseudo: boolean;
  url: string;
  direction: string | null;
  start: string;
  end: string;
  start_hours: number;
  end_hours: number;
  hours_is_default?: boolean;
}

export interface TaskDependency {
  from_key: string;
  to_key: string;
}

export interface EmployeeVacation {
  id: number;
  jira_account_id: string;
  display_name: string;
  start_date: string;
  end_date: string;
}

export interface EpicForecastSnapshot {
  id: number;
  epic_key: string;
  captured_date: string;
  start_date: string;
  hours_per_day: number;
  completion_date: string | null;
  total_issues: number;
  done_issues: number;
  remaining_work_items: number;
  total_planned_hours: number;
  is_pinned: boolean;
}

export interface BuildAndSaveResponse extends SprintBuildResponse {
  sprint: SprintOut;
}

// ---------- Auth ----------

export interface UserOut {
  id: number;
  email: string;
  display_name: string;
  role: string;
  is_active: boolean;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: UserOut;
}

// ---------- Config ----------

/** Запись в team. accountId — это КЛЮЧ словаря team, не поле этого объекта. */
export interface TeamMemberOut {
  /** id строки team_members в БД. У свежедобавленных через UI до сохранения = 0. */
  id: number;
  /** id записи в справочнике people. null до сохранения. */
  person_id: number | null;
  jira_name: string;
  file_name: string;
  role: string;
  salary: number;
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

export interface DirectionOut {
  name: string;
  labels: string[];
  work_types: string[];
  dev_role:     string;
  tester_role:  string;
  analyst_role: string;
  designer_id:  string;
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
  developer_field: string;
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
  directions: DirectionOut[];
}

/** Формат, который шлёт SettingsPage на сервер. team — без id/person_id. */
export interface ConfigUpdate {
  name?: string;
  project_key?: string;
  sprint_field?: string;
  responsible_field?: string;
  hours_per_person?: number;
  default_task_hours?: number;
  leader_hours?: number;
  leader_management_enabled?: boolean;
  developer_field?: string;
  team?: Record<string, { jira_name: string; file_name: string; role: string }>;
  boards?: Record<string, number>;
  extra_components?: string[];
  status_priority?: Record<string, number>;
  role_hours_fields?: Record<string, string>;
  roles?: RoleOut[];
  role_status_buckets?: RoleStatusBucketOut[];
  role_status_default_hours?: RoleStatusDefaultHoursOut[];
  pseudo_tasks?: PseudoTaskOut[];
  terminal_statuses?: string[];
  directions?: DirectionOut[];
}
