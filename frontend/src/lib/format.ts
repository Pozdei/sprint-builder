/** Общие хелперы форматирования дат, чисел и денег. */

/** Сегодняшняя дата в формате ISO `YYYY-MM-DD` (локальная зона). */
export function todayISO(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Полная дата: `2 января 2026`. На вход — ISO `YYYY-MM-DD`. */
export function fmtDateLong(iso: string): string {
  return new Date(iso + "T12:00:00").toLocaleDateString("ru-RU", {
    day: "2-digit", month: "long", year: "numeric",
  });
}

/** Короткая дата: `2 янв`. На вход — ISO `YYYY-MM-DD`. */
export function fmtDateShort(iso: string): string {
  return new Date(iso + "T12:00:00").toLocaleDateString("ru-RU", {
    day: "2-digit", month: "short",
  });
}

/** Числовая дата: `02.01.2026`. На вход — ISO `YYYY-MM-DD`. */
export function fmtDateDotted(iso: string): string {
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}

const _dtFmt = new Intl.DateTimeFormat("ru-RU", {
  year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit",
});

/** Дата и время: `02.01.2026, 14:30`. На вход — полный ISO-таймстамп. */
export function fmtDateTime(iso: string): string {
  return _dtFmt.format(new Date(iso));
}

/** Количество календарных дней от сегодня до даты (отрицательное — в прошлом). */
export function daysUntil(isoDate: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(isoDate + "T00:00:00");
  return Math.ceil((target.getTime() - today.getTime()) / 86400000);
}

/** Число с разрядами по-русски: `1 200 000`. */
export function fmtNum(n: number, fractionDigits = 0): string {
  return n.toLocaleString("ru-RU", { maximumFractionDigits: fractionDigits });
}

/** Сумма в рублях: `1 200 000 ₽`. */
export function fmtRub(n: number, fractionDigits = 0): string {
  return fmtNum(n, fractionDigits) + " ₽";
}
