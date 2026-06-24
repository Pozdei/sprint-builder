import type { IssueFieldsUpdate } from "../api/jira-client";

/** Бакет → поле часов в IssueFieldsUpdate. Код-ревью/Дизайн-ревью/Релиз — без
 * отдельного поля оценки в Jira (константа/веха), туда часы не редактируются отсюда. */
export const BUCKET_TO_FIELD: Partial<Record<string, keyof IssueFieldsUpdate>> = {
  "Анализ":       "hours_analyst",
  "Разработка":   "hours_developer",
  "Тестирование": "hours_tester",
  "Дизайн":       "hours_designer",
};

export const FIELD_LABEL: Record<string, string> = {
  hours_analyst:   "Аналитик",
  hours_developer: "Разработчик",
  hours_tester:    "Тестер",
  hours_designer:  "Дизайнер",
};
