/** Единый перевод названий bucket'ов (этапов конвейера).
 *
 * Ключи карты — рус. строки-идентификаторы, приходящие из бэкенда
 * (`_WORK_TYPE_TO_BUCKET` / `_WORK_TYPE_INFO`); они НЕ переводятся и служат
 * стабильным идентификатором. Переводу подлежит только отображаемый текст —
 * через ключи namespace `gantt`. Все места, где bucket показывается
 * пользователю (Гант, таблица спринта, модалки оценки/конвейера), должны
 * звать `bucketLabel`, чтобы перевод был в одном месте. */
export const BUCKET_LABEL_KEY: Record<string, string> = {
  "Анализ": "gantt:legendAnalysis",
  "Разработка": "gantt:legendDevelopment",
  "Разработка фронт": "gantt:legendDevFront",
  "Разработка бек": "gantt:legendDevBack",
  "Код-ревью": "gantt:legendCodeReview",
  "Тестирование": "gantt:legendTesting",
  "Дизайн": "gantt:legendDesign",
  "Дизайн-ревью": "gantt:legendDesignReview",
  "Релиз": "gantt:legendRelease",
  "Руководство": "gantt:legendManagement",
  "Отсутствие": "gantt:legendAbsence",
  "Отпуск": "gantt:legendVacation",
  "Story": "gantt:legendStory",
  "Epic": "gantt:legendEpic",
  "Консолид.": "gantt:legendConsolidated",
};

/** Перевод названия bucket'а. Неизвестные значения (произвольный текст —
 * например, пользовательский «ожидаемый результат») возвращаются как есть. */
export function bucketLabel(bucket: string, t: (key: string) => string): string {
  const key = BUCKET_LABEL_KEY[bucket];
  return key ? t(key) : bucket;
}
