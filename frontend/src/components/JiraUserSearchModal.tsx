import { useEffect, useState } from "react";
import { searchJiraUsers } from "../api/jira-client";
import type { JiraUserSearchResult } from "../types/intrusions";

interface Props {
  onClose: () => void;
  onPick: (user: JiraUserSearchResult) => void;
}

/** Модальное окно с поиском пользователей по Jira.
 *  Debounce 350ms, минимум 2 символа. */
export function JiraUserSearchModal({ onClose, onPick }: Props) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<JiraUserSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setResults([]);
      setError(null);
      return;
    }
    const t = setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const r = await searchJiraUsers(trimmed);
        setResults(r);
      } catch (e) {
        setError(extractError(e));
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [query]);

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl border w-full max-w-lg p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 className="font-semibold text-gray-800 mb-3">Найти в Jira</h3>

        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          autoFocus
          placeholder="Имя или email…"
          className="w-full px-3 py-2 border rounded mb-3"
        />

        {loading && (
          <div className="text-sm text-gray-500 italic">Ищу…</div>
        )}
        {error && (
          <div className="bg-red-50 border border-red-300 text-red-800 rounded p-2 text-sm mb-2">
            {error}
          </div>
        )}
        {!loading && !error && query.trim().length >= 2 && results.length === 0 && (
          <div className="text-sm text-gray-500">Никого не нашёл.</div>
        )}

        <div className="max-h-80 overflow-y-auto divide-y border rounded">
          {results.map((u) => (
            <button
              key={u.account_id}
              onClick={() => onPick(u)}
              className="w-full text-left px-3 py-2 hover:bg-blue-50 flex items-center gap-3"
            >
              {u.avatar_url && (
                <img
                  src={u.avatar_url}
                  alt=""
                  width={24}
                  height={24}
                  className="rounded-full"
                />
              )}
              <div className="flex-1 min-w-0">
                <div className="text-sm font-semibold text-gray-800 truncate">
                  {u.display_name}
                </div>
                <div className="text-xs text-gray-500 truncate">
                  {u.email || u.account_id}
                </div>
              </div>
            </button>
          ))}
        </div>

        <div className="flex justify-end mt-3">
          <button
            type="button"
            onClick={onClose}
            className="bg-gray-300 hover:bg-gray-400 text-gray-700 px-3 py-1.5 rounded text-sm"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}

function extractError(e: unknown): string {
  if (e && typeof e === "object" && "response" in e) {
    const r = (e as { response?: { data?: { detail?: string } } }).response;
    if (r?.data?.detail) return r.data.detail;
  }
  if (e instanceof Error) return e.message;
  return String(e);
}
