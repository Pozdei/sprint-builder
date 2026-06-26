import { useTranslation } from "react-i18next";
import type { RoleOut } from "../../types/api";

interface Props {
  value: RoleOut[];
  onChange: (next: RoleOut[]) => void;
}

export function RolesEditor({ value, onChange }: Props) {
  const { t } = useTranslation(["settings", "common"]);
  const updateField = (i: number, field: keyof RoleOut, val: unknown) => {
    const next = [...value];
    next[i] = { ...next[i], [field]: val };
    onChange(next);
  };

  const handleAdd = () => {
    onChange([
      ...value,
      {
        name: t("roles.newRoleName"),
        display_name: t("roles.newRoleDisplayName"),
        enabled: false,
        is_lead: false,
        sort_order: value.length,
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
            <th className="text-left px-2 py-1 border-b font-semibold">{t("roles.table.name")}</th>
            <th className="text-left px-2 py-1 border-b font-semibold">{t("roles.table.displayName")}</th>
            <th className="text-center px-2 py-1 border-b font-semibold">{t("roles.table.inSprint")}</th>
            <th className="text-center px-2 py-1 border-b font-semibold">{t("roles.table.lead")}</th>
            <th className="px-2 py-1 border-b w-12"></th>
          </tr>
        </thead>
        <tbody>
          {value.map((r, i) => (
            <tr key={i} className="border-b">
              <td className="px-2 py-1">
                <input
                  type="text"
                  value={r.name}
                  onChange={(e) => updateField(i, "name", e.target.value)}
                  className="w-full px-2 py-1 border rounded font-mono text-xs"
                />
              </td>
              <td className="px-2 py-1">
                <input
                  type="text"
                  value={r.display_name}
                  onChange={(e) => updateField(i, "display_name", e.target.value)}
                  className="w-full px-2 py-1 border rounded"
                />
              </td>
              <td className="px-2 py-1 text-center">
                <input
                  type="checkbox"
                  checked={r.enabled}
                  onChange={(e) => updateField(i, "enabled", e.target.checked)}
                />
              </td>
              <td className="px-2 py-1 text-center">
                <input
                  type="checkbox"
                  checked={r.is_lead}
                  onChange={(e) => updateField(i, "is_lead", e.target.checked)}
                />
              </td>
              <td className="px-2 py-1 text-center">
                <button
                  onClick={() => handleRemove(i)}
                  className="text-red-500 hover:text-red-700 text-lg"
                  title={t("roles.remove")}
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
        {t("roles.addRole")}
      </button>
    </div>
  );
}
