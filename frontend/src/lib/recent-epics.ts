/** Память последних введённых ключей эпиков — хранится в localStorage,
 *  переживает перезагрузку и закрытие вкладки. */

const STORAGE_KEY = "sprint-builder.recent-epics";
const MAX_ITEMS = 8;

/** Прочитать список недавних эпиков (самый свежий — первый). */
export function loadRecentEpics(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

/** Добавить ключ в начало списка (без дублей), вернуть обновлённый список. */
export function pushRecentEpic(key: string): string[] {
  const k = key.trim().toUpperCase();
  if (!k) return loadRecentEpics();
  const next = [k, ...loadRecentEpics().filter((x) => x !== k)].slice(0, MAX_ITEMS);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // приватный режим / переполнение — не критично
  }
  return next;
}

/** Удалить один ключ из списка, вернуть обновлённый. */
export function removeRecentEpic(key: string): string[] {
  const next = loadRecentEpics().filter((x) => x !== key);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // не критично
  }
  return next;
}
