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
  hours_designer?: number | null;
  hours_original?: number | null;
  hours_is_default?: boolean;
  overflow_reason?: string | null;
  designer_id?: string | null;
  tester_id?: string | null;
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
  spent_hours?: number;
  spent_cost?: number;
  remaining_hours?: number;
  remaining_cost?: number;
}

export interface CostBreakdownItem {
  name: string;
  hours: number;
  salary: number;
  cost: number;
}

export type MissingRole = "responsible" | "developer" | "designer" | "tester";

export interface MissingAssigneeItem {
  key: string;
  url: string;
  summary: string;
  direction: string | null;
  missing: MissingRole[];
  responsible_id: string | null;
  developer_id: string | null;
  designer_id: string | null;
  tester_id: string | null;
}

export interface EpicForecastResponse {
  epic_key: string;
  epic_summary: string;
  gantt_items: GanttItem[];
  completion_date: string | null;
  stats: EpicStats;
  cost_breakdown: CostBreakdownItem[];
  warnings: string[];
  gantt_start?: string | null;
  today_hours?: number | null;
  current_sprint?: CurrentSprint | null;
  missing_assignees: MissingAssigneeItem[];
}

export interface CurrentSprint {
  sprint_num: number | null;
  start_date: string;
  end_date: string;
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
  is_historical?: boolean;
  phase_status?: string | null;
  phase_cost?: number;
  parent_key?: string | null;
  parent_summary?: string | null;
  story_key?: string | null;
  story_summary?: string | null;
  epic_key?: string | null;
  epic_summary?: string | null;
}

export interface TaskDependency {
  from_key: string;
  to_key: string;
  /** Этап (bucket); пусто/undefined = вся задача (последний этап A -> первый этап B). */
  from_bucket?: string | null;
  to_bucket?: string | null;
  /** Реальный scope (epic_key), под которым зависимость лежит в БД — заполняется
   * сервером при чтении; нужен, чтобы удаление унаследованной (из меньшего
   * подмножества родителей) зависимости попадало в нужную запись. */
  epic_key?: string | null;
}

export interface RootTaskOut {
  owner_id: string;
  task_key: string;
}

export interface GanttSnapshotSummary {
  id: number;
  captured_at: string;
  label: string | null;
  gantt_start: string;
  hours_per_day: number;
}

export interface GanttSnapshotDetail extends GanttSnapshotSummary {
  gantt_items: GanttItem[];
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
  /** work_type -> имя роли; пусто/нет ключа = системный дефолт */
  role_overrides: Record<string, string>;
  designer_id: string;
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
  designer_field: string;
  tester_field: string;
  /** Подключение к Jira; пусто = берётся из .env сервера. Токен не возвращается. */
  jira_base_url: string;
  jira_email: string;
  jira_api_token_set: boolean;
  /** Telegram-дайджест. Токен бота per-конфиг (write-only), fallback на .env. */
  telegram_chat_id: string;
  telegram_daily_enabled: boolean;
  telegram_daily_time: string;
  /** Задан ли токен на самом конфиге. */
  telegram_bot_token_set: boolean;
  /** Доступна ли отправка вообще (токен конфига или .env). */
  telegram_bot_configured: boolean;
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
  designer_field?: string;
  tester_field?: string;
  jira_base_url?: string;
  jira_email?: string;
  /** Шлём только если пользователь ввёл новое значение; "" — явно очистить. */
  jira_api_token?: string;
  telegram_chat_id?: string;
  telegram_daily_enabled?: boolean;
  telegram_daily_time?: string;
  /** Шлём только если ввели новое значение; "" — явно очистить (вернётся к .env). */
  telegram_bot_token?: string;
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
