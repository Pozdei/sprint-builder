/** Сгруппировать элементы по строковому ключу. Falsy-ключи отбрасываются (нет группы). */
export function groupBy<T>(items: T[], keyFn: (t: T) => string | null | undefined): Record<string, T[]> {
  const m: Record<string, T[]> = {};
  for (const it of items) {
    const k = keyFn(it);
    if (!k) continue;
    (m[k] ??= []).push(it);
  }
  return m;
}
