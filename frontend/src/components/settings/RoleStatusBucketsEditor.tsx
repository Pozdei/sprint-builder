import type { RoleOut, RoleStatusBucketOut } from "../../types/api";

interface Props {
  value: RoleStatusBucketOut[];
  onChange: (next: RoleStatusBucketOut[]) => void;
  roles: RoleOut[];
  /** Список бакетов для dropdown. */
  buckets: string[];
}

export function RoleStatusBucketsEditor({ value, onChange, roles, buckets }: Props) {
  const update = (i: number, field: keyof RoleStatusBucketOut, v: string) => {
    const next = [...value];
    next[i] = { ...next[i], [field]: v };
    onChange(next);
  };

  const handleAdd = () => {
    onChange([
      ...value,
      {
        role: roles[0]?.name || "analyst",
        jira_status: "",
        bucket: buckets[0] || "",
      },
    ]);
  };

  const handleRemove = (i: number) => {
    onChange(value.filter((_, idx) => idx !== i));
  };

  return (
    <div>
      <table className="w-full text-sm border">
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left px-2 py-1 border-b font-semibold w-1/4">Роль</th>
            <th className="text-left px-2 py-1 border-b font-semibold w-1/3">Статус Jira</th>
            <th className="text-left px-2 py-1 border-b font-semibold w-1/3">Бакет</th>
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
                  type="text"
                  list="buckets-list"
                  value={r.bucket}
                  onChange={(e) => update(i, "bucket", e.target.value)}
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
      <datalist id="buckets-list">
        {buckets.map((b) => (
          <option key={b} value={b} />
        ))}
      </datalist>
      <button
        onClick={handleAdd}
        className="mt-2 text-sm text-blue-600 hover:text-blue-800"
      >
        + Добавить
      </button>
    </div>
  );
}
