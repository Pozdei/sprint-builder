// Дополнительные типы для multi-config (фаза 2.8).

export interface ConfigSummary {
  id: number;
  name: string;
  is_active: boolean;
}

export interface ConfigCreateRequest {
  name: string;
  source_config_id: number | null;
}

export interface ConfigTemplate {
  id: number;
  name: string;
}
