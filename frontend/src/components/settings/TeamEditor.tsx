import { useState } from "react";
import type { TeamMember } from "../../types/api";

interface Props {
  value: Record<string, TeamMember>;
  onChange: (next: Record<string, TeamMember>) => void;
}

export function TeamEditor({ value, onChange }: Props) {
  const [accountIds, setAccountIds] = useState<string[]>(() => Object.keys(value));

  const handleAccountIdChange = (i: number, newId: string) => {
    const oldId = accountIds[i];
    const newIds = [...accountIds];
    newIds[i] = newId;
    setAccountIds(newIds);
    const next: Record<string, TeamMember> = {};
    newIds.forEach((id, idx) => {
      const source = idx === i ? oldId : id;
      next[id] = value[source];
    });
    onChange(next);
  };

  const handleFieldChange = (i: number, field: "jira_name" | "file_name", v: string) => {
    const id = accountIds[i];
    onChange({ ...value, [id]: { ...value[id], [field]: v } });
  };

  const handleAdd = () => {
    const newId = `новый_account_id_${Date.now()}`;
    setAccountIds([...accountIds, newId]);
    onChange({ ...value, [newId]: { jira_name: "", file_name: "" } });
  };

  const handleRemove = (i: number) => {
    const id = accountIds[i];
    const newIds = accountIds.filter((_, idx) => idx !== i);
    setAccountIds(newIds);
    const next = { ...value };
    delete next[id];
    onChange(next);
  };

  return (
    <div>
      <table className="w-full text-sm border">
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left px-2 py-1 border-b font-semibold">accountId Jira</th>
            <th className="text-left px-2 py-1 border-b font-semibold">Имя в Jira</th>
            <th className="text-left px-2 py-1 border-b font-semibold">Имя в файле</th>
            <th className="px-2 py-1 border-b w-12"></th>
          </tr>
        </thead>
        <tbody>
          {accountIds.map((id, i) => (
            <tr key={i} className="border-b">
              <td className="px-2 py-1">
                <input
                  type="text"
                  value={id}
                  onChange={(e) => handleAccountIdChange(i, e.target.value)}
                  className="w-full px-2 py-1 border rounded font-mono text-xs"
                  spellCheck={false}
                />
              </td>
              <td className="px-2 py-1">
                <input
                  type="text"
                  value={value[id]?.jira_name || ""}
                  onChange={(e) => handleFieldChange(i, "jira_name", e.target.value)}
                  className="w-full px-2 py-1 border rounded"
                />
              </td>
              <td className="px-2 py-1">
                <input
                  type="text"
                  value={value[id]?.file_name || ""}
                  onChange={(e) => handleFieldChange(i, "file_name", e.target.value)}
                  className="w-full px-2 py-1 border rounded"
                />
              </td>
              <td className="px-2 py-1 text-center">
                <button
                  onClick={() => handleRemove(i)}
                  className="text-red-500 hover:text-red-700 text-lg"
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
        onClick={handleAdd}
        className="mt-2 text-sm text-blue-600 hover:text-blue-800"
      >
        + Добавить участника
      </button>
    </div>
  );
}
