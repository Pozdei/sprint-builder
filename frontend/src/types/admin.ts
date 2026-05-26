// Типы для админских эндпоинтов.

export interface UserCreateRequest {
  email: string;
  display_name?: string;
  role: string;
  password: string;
}

export interface UserUpdateRequest {
  display_name?: string;
  role?: string;
  is_active?: boolean;
}

export interface AdminConfigSummary {
  id: number;
  name: string;
  owner_user_id: number | null;
  owner_email: string | null;
  owner_display_name: string | null;
  sprints_count: number;
}

export interface AdminSprintSummary {
  id: number;
  sprint_num: number;
  status: string;
  config_id: number | null;
  owner_email: string | null;
}

export interface AdminTeamMember {
  account_id: string;
  jira_name: string;
  file_name: string;
  role: string;
  salary: number;
}
