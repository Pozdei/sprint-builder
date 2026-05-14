import type { RoleOut, RoleStatusDefaultHoursOut } from "../../types/api";

interface Props {
  value: RoleStatusDefaultHoursOut[];
  onChange: (next: RoleStatusDefaultHoursOut[]) => void;
  roles: RoleOut[];
}

export function RoleStatusHoursEditor({ value, onChange, roles }: Props) {
  const update = (i: number, field: keyof RoleStatusDefaultHoursOut, v: string | number) => {
    const next = [...value];
    next[i] = { ...next[i], [field]: v } as RoleStatusDefaultHoursOut;
    onChange(next);
  };

  const handleAdd = () => {
    onChange([
      ...value,
      { role: roles[0]?.name || "analyst", jira_status: "", hours: 1 },
    ]);
  };

  const handleRemove = (i: number) => onChange(value.filter((_, idx) => idx !== i));

  return (
    <div>
      <table className="w-full text-sm border">
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left px-2 py-1 border-b font-semibold w-1/3">Роль</th>
            <th className="text-left px-2 py-1 border-b font-semibold w-1/3">Статус Jira</th>
            <th className="text-left px-2 py-1 border-b font-semibold w-1/4">Часы</th>
            <th className="px-2 py-1 border-b w-12"></th>
          </tr>
        </thead>
        <tbody>
          {value.map((r, i) => (
            <tr key={i} className="border-b">
              <td className="px-2 py-1">
                <select
                  value={r.role}
                  onChange={(e) => update(i, "role", e.target.value)}
                  className="w-full px-2 py-1 border rounded bg-white"
                >
                  {roles.map((role) => (
                    <option key={role.name} value={role.name}>
                      {role.display_name}
                    </option>
                  ))}
                </select>
              </td>
              <td className="px-2 py-1">
                <input
                  type="text"
                  value={r.jira_status}
                  onChange={(e) => update(i, "jira_status", e.target.value)}
                  className="w-full px-2 py-1 border rounded"
                />
              </td>
              <td className="px-2 py-1">
                <input
                  type="number"
                  step="0.5"
                  value={r.hours}
                  onChange={(e) => update(i, "hours", Number(e.target.value))}
                  className="w-full px-2 py-1 border rounded"
                />
              </td>
              <td className="px-2 py-1 text-center">
                <button
                  onClick={() => handleRemove(i)}
                  className="text-red-500 hover:text-red-700 text-lg"
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
        + Добавить
      </button>
    </div>
  );
}
