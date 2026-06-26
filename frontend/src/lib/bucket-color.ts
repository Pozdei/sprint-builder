/** Единая палитра bucket'ов (этапов конвейера).
 *
 * Один источник цвета на этап для всех представлений: Гант (inline hex),
 * таблица спринта, модалка стендапа, модалка конвейера (Tailwind-классы).
 * Tailwind-классы заданы строковыми литералами намеренно — JIT не умеет
 * собирать имена классов динамически (`bg-${x}-50` будет вычищен из бандла).
 *
 * Ключи — рус. строки-идентификаторы bucket'ов, приходящие из бэкенда
 * (см. backend `app/sprint/buckets.py`). Перевод отображаемого текста — в
 * `bucket-label.ts`; здесь только цвета. */

export interface BucketColor {
  /** hex для inline-стилей SVG-Ганта. */
  hex: { bg: string; text: string; border: string };
  /** Tailwind: точка-маркер этапа. */
  dot: string;
  /** Tailwind: мягкий фон (bg-*-50) — ячейки таблицы, строки конвейера. */
  softBg: string;
  /** Tailwind: текст к мягкому фону. */
  softText: string;
  /** Tailwind: насыщенный бейдж (bg-*-100 text-*-800). */
  solid: string;
}

const C = (
  bg: string, text: string, border: string,
  dot: string, softBg: string, softText: string, solid: string,
): BucketColor => ({ hex: { bg, text, border }, dot, softBg, softText, solid });

const DEFAULT: BucketColor = C(
  "#f3f4f6", "#374151", "#9ca3af",
  "bg-gray-400", "bg-gray-50", "text-gray-700", "bg-gray-100 text-gray-700",
);

const BUCKET_COLORS: Record<string, BucketColor> = {
  "Анализ":           C("#fef3c7", "#92400e", "#d97706", "bg-amber-400",   "bg-amber-50",   "text-amber-800",   "bg-amber-100 text-amber-800"),
  "Разработка":       C("#d1fae5", "#065f46", "#059669", "bg-green-500",   "bg-green-50",   "text-green-800",   "bg-green-100 text-green-800"),
  "Разработка фронт": C("#bbf7d0", "#14532d", "#22c55e", "bg-green-500",   "bg-green-50",   "text-green-800",   "bg-green-100 text-green-800"),
  "Разработка бек":   C("#c7d2fe", "#312e81", "#6366f1", "bg-indigo-500",  "bg-indigo-50",  "text-indigo-800",  "bg-indigo-100 text-indigo-800"),
  "Код-ревью":        C("#a7f3d0", "#064e3b", "#047857", "bg-emerald-500", "bg-emerald-50", "text-emerald-800", "bg-emerald-100 text-emerald-800"),
  "Тестирование":     C("#dbeafe", "#1e3a5f", "#2563eb", "bg-blue-500",    "bg-blue-50",    "text-blue-800",    "bg-blue-100 text-blue-800"),
  "Дизайн":           C("#fce7f3", "#831843", "#db2777", "bg-pink-500",    "bg-pink-50",    "text-pink-800",    "bg-pink-100 text-pink-800"),
  "Дизайн-ревью":     C("#f5d0fe", "#581c87", "#a855f7", "bg-fuchsia-500", "bg-fuchsia-50", "text-fuchsia-800", "bg-fuchsia-100 text-fuchsia-800"),
  "Релиз":            C("#fef9c3", "#713f12", "#ca8a04", "bg-yellow-500",  "bg-yellow-50",  "text-yellow-800",  "bg-yellow-100 text-yellow-800"),
  "Руководство":      C("#ede9fe", "#4c1d95", "#7c3aed", "bg-purple-500",  "bg-purple-50",  "text-purple-800",  "bg-purple-100 text-purple-800"),
  "Отсутствие":       C("#f3f4f6", "#374151", "#9ca3af", "bg-gray-400",    "bg-gray-100",   "text-gray-700",    "bg-gray-100 text-gray-700"),
  "Отпуск":           C("#fff7ed", "#9a3412", "#f97316", "bg-orange-500",  "bg-orange-50",  "text-orange-800",  "bg-orange-100 text-orange-800"),
  "Story":            C("#e0e7ff", "#3730a3", "#6366f1", "bg-indigo-500",  "bg-indigo-50",  "text-indigo-800",  "bg-indigo-100 text-indigo-800"),
  "Epic":             C("#ddd6fe", "#5b21b6", "#7c3aed", "bg-violet-500",  "bg-violet-50",  "text-violet-800",  "bg-violet-100 text-violet-800"),
  "Консолид.":        C("#ccfbf1", "#115e59", "#14b8a6", "bg-teal-500",    "bg-teal-50",    "text-teal-800",    "bg-teal-100 text-teal-800"),
};

/** Цвет bucket'а во всех представлениях. Неизвестные → нейтральный серый. */
export function bucketColor(bucket: string): BucketColor {
  return BUCKET_COLORS[bucket] ?? DEFAULT;
}

/** Известен ли bucket в палитре (есть ли у него собственный цвет). */
export function isKnownBucket(bucket: string): boolean {
  return bucket in BUCKET_COLORS;
}

/** Все bucket'ы палитры в порядке объявления — для легенды Ганта. */
export const BUCKET_NAMES: string[] = Object.keys(BUCKET_COLORS);

/** Мягкий фон+текст одной строкой (для ячеек/бейджей с лёгким фоном). */
export function bucketSoftClass(bucket: string): string {
  const c = bucketColor(bucket);
  return `${c.softBg} ${c.softText}`;
}

/** Дефолтный порядок этапов конвейера (зеркало backend DEFAULT_BUCKET_PIPELINE). */
export const BUCKET_PIPELINE_ORDER = [
  "Анализ", "Дизайн", "Разработка", "Код-ревью", "Дизайн-ревью", "Тестирование", "Релиз",
];
