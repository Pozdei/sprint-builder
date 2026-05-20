import { useState } from "react";
import { JiraUserSearchModal } from "../JiraUserSearchModal";
import type { TeamMemberOut } from "../../types/api";
import type { JiraUserSearchResult } from "../../types/intrusions";

interface Props {
  value: Record<string, TeamMemberOut>;
  onChange: (next: Record<string, TeamMemberOut>) => void;
  roleOptions: { name: string; display_name: string }[];
}

export function TeamEditor({ value, onChange, roleOptions }: Props) {
  const [searchOpen, setSearchOpen] = useState(false);

  const handlePickFromJira = (user: JiraUserSearchResult) => {
    const accId = user.account_id;
    if (!accId) return;
    if (value[accId]) {
      setSearchOpen(false);
      return;
    }
    const next: Record<string, TeamMemberOut> = {
      ...value,
      [accId]: {
        id: 0,
        person_id: null,
        jira_name: user.display_name,
        file_name: "",
        role: roleOptions[0]?.name || "analyst",
      },
    };
    onChange(next);
    setSearchOpen(false);
  };

  const handleRemove = (accId: string) => {
    if (!window.confirm("Удалить человека из команды?")) return;
    const next = { ...value };
    delete next[accId];
    onChange(next);
  };

  const updateField = (
    accId: string,
    field: "file_name" | "role",
    val: string,
  ) => {
    onChange({
      ...value,
      [accId]: { ...value[accId], [field]: val },
    });
  };

  const rows = Object.entries(value);

  return (
    <div>
      <table className="w-full text-sm bg-white border rounded-lg overflow-hidden">
        <thead className="bg-gray-100 border-b">
          <tr>
            <th className="text-left px-3 py-1.5">Имя в Jira</th>
            <th className="text-left px-3 py-1.5 w-48">Имя для файла</th>
            <th className="text-left px-3 py-1.5 w-40">Роль</th>
            <th className="text-left px-3 py-1.5 w-64">accountId</th>
            <th className="w-10"></th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={5} className="text-center text-gray-400 py-3 italic">
                Команда пуста. Добавьте через «+ Добавить из Jira».
              </td>
            </tr>
          )}
          {rows.map(([accId, m]) => (
            <tr key={accId} className="border-b">
              <td className="px-3 py-1.5">{m.jira_name}</td>
              <td className="px-3 py-1.5">
                <input
                  type="text"
                  value={m.file_name}
                  onChange={(e) => updateField(accId, "file_name", e.target.value)}
                  placeholder="напр. Бадамова А."
                  className="w-full px-2 py-1 border rounded text-sm"
                />
              </td>
              <td className="px-3 py-1.5">
                <select
                  value={m.role}
                  onChange={(e) => updateField(accId, "role", e.target.value)}
                  className="w-full px-2 py-1 border rounded text-sm bg-white"
                >
                  {roleOptions.map((r) => (
                    <option key={r.name} value={r.name}>
                      {r.display_name}
                    </option>
                  ))}
                </select>
              </td>
              <td className="px-3 py-1.5 font-mono text-xs text-gray-500 truncate"
                  title={accId}>
                {accId}
              </td>
              <td className="text-center px-3 py-1.5">
                <button
                  onClick={() => handleRemove(accId)}
                  className="text-red-500 hover:text-red-700"
                  title="Удалить"
                >
                  ×
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <button
        onClick={() => setSearchOpen(true)}
        className="mt-2 bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded text-sm font-semibold"
      >
        + Добавить из Jira
      </button>

      {searchOpen && (
        <JiraUserSearchModal
          onClose={() => setSearchOpen(false)}
          onPick={handlePickFromJira}
        />
      )}
    </div>
  );
}
