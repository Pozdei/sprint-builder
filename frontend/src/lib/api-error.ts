/** Извлекает человекочитаемое сообщение об ошибке из ответа axios / Error. */
export function extractError(e: unknown, fallback = "Ошибка"): string {
  if (e && typeof e === "object" && "response" in e) {
    const r = (e as { response?: { data?: { detail?: string } } }).response;
    if (r?.data?.detail) return r.data.detail;
  }
  if (e instanceof Error) return e.message;
  return fallback;
}
