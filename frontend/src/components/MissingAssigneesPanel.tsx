import { useState } from "react";
import { type IssueFieldsUpdate, updateJiraIssueFields } from "../api/jira-client";
import { extractError } from "../lib/api-error";
import type { JiraUserSearchResult } from "../types/intrusions";
import type { MissingAssigneeItem, MissingRole } from "../types/api";
import { JiraUserSearchModal } from "./JiraUserSearchModal";
import { useToast } from "./Toast";

const ROLE_LABELS: Record<MissingRole, string> = {
  responsible: "Аналитик",
  developer: "Разработчик",
  designer: "Дизайнер",
  tester: "Тестировщик",
};

const ROLE_COLORS: Record<MissingRole, string> = {
  responsible: "bg-blue-50 border-blue-300 text-blue-700",
  developer: "bg-emerald-50 border-emerald-300 text-emerald-700",
  designer: "bg-pink-50 border-pink-300 text-pink-700",
  tester: "bg-amber-50 border-amber-300 text-amber-700",
};

function buildUpdate(role: MissingRole, accountId: string): IssueFieldsUpdate {
  switch (role) {
    case "responsible": return { responsible_account_id: accountId };
    case "developer": return { developer_account_id: accountId };
    case "designer": return { designer_account_id: accountId };
    case "tester": return { tester_account_id: accountId };
  }
}

interface Props {
  items: MissingAssigneeItem[];
  onAssigned: (key: string, role: MissingRole) => void;
}

export function MissingAssigneesPanel({ items, onAssigned }: Props) {
  const toast = useToast();
  const [picking, setPicking] = useState<{ key: string; role: MissingRole } | null>(null);
  const [saving, setSaving] = useState<string | null>(null);

  const handlePick = async (user: JiraUserSearchResult) => {
    if (!picking) return;
    const { key, role } = picking;
    const cell = `${key}:${role}`;
    setPicking(null);
    setSaving(cell);
    try {
      await updateJiraIssueFields(key, buildUpdate(role, user.account_id));
      toast.success(`${key}: ${ROLE_LABELS[role]} — ${user.display_name}`);
      onAssigned(key, role);
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setSaving(null);
    }
  };

  if (items.length === 0) {
    return (
      <div className="text-center text-gray-400 py-10">
        Все задачи направлений design/development обеспечены исполнителями.
      </div>
    );
  }

  return (
    <>
      <div className="bg-white rounded-xl border shadow-sm overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b">
            <tr>
              <th className="text-left px-3 py-2 font-semibold">Задача</th>
              <th className="text-left px-3 py-2 font-semibold">Название</th>
              <th className="text-left px-3 py-2 font-semibold">Направление</th>
              <th className="text-left px-3 py-2 font-semibold">Кого не хватает</th>
            </tr>
          </thead>
          <tbody>
            {items.map((it) => (
              <tr key={it.key} className="border-b hover:bg-gray-50 align-top">
                <td className="px-3 py-2">
                  <a
                    href={it.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-600 hover:underline font-mono text-xs"
                  >
                    {it.key}
                  </a>
                </td>
                <td className="px-3 py-2 text-gray-700 max-w-md truncate" title={it.summary}>
                  {it.summary}
                </td>
                <td className="px-3 py-2 text-gray-500">{it.direction ?? "—"}</td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-1.5">
                    {it.missing.map((role) => {
                      const cell = `${it.key}:${role}`;
                      return (
                        <button
                          key={role}
                          onClick={() => setPicking({ key: it.key, role })}
                          disabled={saving === cell}
                          className={`px-2 py-1 rounded-lg text-xs font-medium border transition hover:opacity-80 disabled:opacity-50 ${ROLE_COLORS[role]}`}
                        >
                          {saving === cell ? "Сохраняю…" : `+ ${ROLE_LABELS[role]}`}
                        </button>
                      );
                    })}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {picking && (
        <JiraUserSearchModal onClose={() => setPicking(null)} onPick={handlePick} />
      )}
    </>
  );
}
