import { useTranslation } from "react-i18next";
import { useToast } from "../Toast";
import type { PseudoTaskOut, TeamMemberOut } from "../../types/api";

interface Props {
  value: PseudoTaskOut[];
  onChange: (next: PseudoTaskOut[]) => void;
  team: Record<string, TeamMemberOut>;
}

export function PseudoTasksEditor({ value, onChange, team }: Props) {
  const { t } = useTranslation(["settings", "common"]);
  const toast = useToast();
  // Берём только сохранённых (id > 0). У свежедобавленных через "+ Добавить из Jira"
  // id = 0 — для них псевдо-задачи нельзя завести до сохранения конфига.
  const members = Object.entries(team)
    .map(([accId, m]) => ({ accId, ...m }))
    .filter((m) => m.id > 0);

  const memberById = new Map(members.map((m) => [m.id, m]));
  const hasUnsavedMembers = Object.values(team).some((m) => !m.id || m.id <= 0);

  const update = (
    i: number,
    field: keyof PseudoTaskOut,
    v: string | number | boolean | null,
  ) => {
    const next = [...value];
    next[i] = { ...next[i], [field]: v } as PseudoTaskOut;
    onChange(next);
  };

  const handleAdd = () => {
    if (members.length === 0) {
      toast.info(t("pseudoTasks.noSavedMembers"));
      return;
    }
    onChange([
      ...value,
      {
        member_id: members[0].id,
        name: t("pseudoTasks.newTask.name"),
        bucket: t("pseudoTasks.newTask.bucket"),
        hours: 40,
        recurring: false,
        target_sprint_num: null,
      },
    ]);
  };

  const handleRemove = (i: number) => onChange(value.filter((_, idx) => idx !== i));

  return (
    <div>
      {hasUnsavedMembers && (
        <div className="mb-3 bg-yellow-50 border border-yellow-300 text-yellow-900 rounded p-2 text-sm">
          {t("pseudoTasks.unsavedMembersWarning")}
        </div>
      )}

      <table className="w-full text-sm border">
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left px-2 py-1 border-b font-semibold">{t("pseudoTasks.table.person")}</th>
            <th className="text-left px-2 py-1 border-b font-semibold">{t("pseudoTasks.table.name")}</th>
            <th className="text-left px-2 py-1 border-b font-semibold">{t("pseudoTasks.table.bucket")}</th>
            <th className="text-left px-2 py-1 border-b font-semibold w-20">{t("pseudoTasks.table.hours")}</th>
            <th className="text-center px-2 py-1 border-b font-semibold w-24">{t("pseudoTasks.table.recurring")}</th>
            <th className="text-left px-2 py-1 border-b font-semibold w-32">{t("pseudoTasks.table.sprintNum")}</th>
            <th className="px-2 py-1 border-b w-12"></th>
          </tr>
        </thead>
        <tbody>
          {value.map((pt, i) => {
            const m = memberById.get(pt.member_id);
            return (
              <tr key={i} className="border-b">
                <td className="px-2 py-1">
                  <select
                    value={pt.member_id}
                    onChange={(e) => update(i, "member_id", Number(e.target.value))}
                    className="w-full px-2 py-1 border rounded bg-white"
                  >
                    {!m && pt.member_id ? (
                      <option value={pt.member_id}>
                        {t("pseudoTasks.memberNotFound", { id: pt.member_id })}
                      </option>
                    ) : null}
                    {members.map((mem) => (
                      <option key={mem.id} value={mem.id}>
                        {mem.file_name || mem.jira_name} ({mem.role})
                      </option>
                    ))}
                  </select>
                </td>
                <td className="px-2 py-1">
                  <input
                    type="text"
                    value={pt.name}
                    onChange={(e) => update(i, "name", e.target.value)}
                    className="w-full px-2 py-1 border rounded"
                  />
                </td>
                <td className="px-2 py-1">
                  <input
                    type="text"
                    value={pt.bucket}
                    onChange={(e) => update(i, "bucket", e.target.value)}
                    placeholder={t("pseudoTasks.bucketPlaceholder")}
                    className="w-full px-2 py-1 border rounded"
                  />
                </td>
                <td className="px-2 py-1">
                  <input
                    type="number"
                    step="0.5"
                    value={pt.hours}
                    onChange={(e) => update(i, "hours", Number(e.target.value))}
                    onWheel={(e) => e.currentTarget.blur()}
                    className="w-full px-2 py-1 border rounded"
                  />
                </td>
                <td className="px-2 py-1 text-center">
                  <input
                    type="checkbox"
                    checked={pt.recurring}
                    onChange={(e) => update(i, "recurring", e.target.checked)}
                  />
                </td>
                <td className="px-2 py-1">
                  <input
                    type="number"
                    value={pt.target_sprint_num ?? ""}
                    placeholder={t("pseudoTasks.sprintNumPlaceholder")}
                    onChange={(e) => {
                      const v = e.target.value;
                      update(i, "target_sprint_num", v === "" ? null : Number(v));
                    }}
                    onWheel={(e) => e.currentTarget.blur()}
                    className="w-full px-2 py-1 border rounded"
                    disabled={pt.recurring}
                    title={pt.recurring
                      ? t("pseudoTasks.sprintNumTitleRecurring")
                      : t("pseudoTasks.sprintNumTitleOnce")}
                  />
                </td>
                <td className="px-2 py-1 text-center">
                  <button
                    onClick={() => handleRemove(i)}
                    className="text-red-500 hover:text-red-700 text-lg"
                    title={t("pseudoTasks.remove")}
                  >
                    ×
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <button
        onClick={handleAdd}
        className="mt-2 text-sm text-blue-600 hover:text-blue-800"
      >
        {t("pseudoTasks.add")}
      </button>
      <p className="text-xs text-gray-500 mt-2">
        <b>{t("pseudoTasks.table.recurring")}</b> — {t("pseudoTasks.footnoteRecurring")}<br />
        <b>{t("pseudoTasks.table.sprintNum")}</b> — {t("pseudoTasks.footnoteSprintNum")}<br />
        {t("pseudoTasks.footnoteManagement")}
      </p>
    </div>
  );
}
