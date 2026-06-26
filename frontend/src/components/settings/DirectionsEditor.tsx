import { useTranslation } from "react-i18next";
import type { DirectionOut, RoleOut, TeamMemberOut } from "../../types/api";

// Зеркало backend _WORK_TYPE_INFO (app/sprint/logic.py) — только для отображения.
// role/bucket-имена ключей здесь технические (используются как i18n-ключи в directions.buckets.*).
const WORK_TYPE_INFO: Record<string, { role: string; bucketKey: string }> = {
  analytics:     { role: "analyst",        bucketKey: "analytics" },
  development:   { role: "developer",      bucketKey: "development" },
  testing:       { role: "analyst",        bucketKey: "testing" },
  design:        { role: "designer",       bucketKey: "design" },
  code_review:   { role: "developer_lead", bucketKey: "code_review" },
  design_review: { role: "designer_lead",  bucketKey: "design_review" },
  release:       { role: "developer_lead", bucketKey: "release" },
};

// Виды работ, для которых backend учитывает переопределение роли (role_overrides).
const OVERRIDABLE_WORK_TYPES = new Set(["development", "testing", "analytics"]);

const ALL_WORK_TYPES = Object.keys(WORK_TYPE_INFO);

interface Props {
  value: DirectionOut[];
  onChange: (next: DirectionOut[]) => void;
  roles?: RoleOut[];
  team?: Record<string, TeamMemberOut>;
}

export function DirectionsEditor({ value, onChange, roles = [], team = {} }: Props) {
  const { t } = useTranslation(["settings", "common"]);
  const devRoleOptions     = roles.filter((r) => !r.is_lead && r.name !== "analyst" && r.name !== "designer");
  const contentRoleOptions = roles.filter((r) => !r.is_lead && r.name !== "designer" && !r.name.startsWith("developer"));
  const designerMembers    = Object.entries(team).filter(([, m]) => m.role === "designer");

  // "developer" в WORK_TYPE_INFO — не настоящая роль, а обобщённое имя для любой
  // роли разработчика (developer_backend/frontend/lead) — её нет в списке ролей конфига,
  // поэтому даём отдельную человекочитаемую подпись.
  const roleDisplayName = (roleName: string | undefined): string => {
    if (!roleName) return t("directions.noValue");
    const found = roles.find((r) => r.name === roleName)?.display_name;
    if (found) return found;
    if (roleName === "developer") return t("directions.genericRole.developer");
    return roleName;
  };

  const updateField = (i: number, field: keyof DirectionOut, val: unknown) => {
    const next = [...value];
    next[i] = { ...next[i], [field]: val };
    onChange(next);
  };

  const updateOverride = (dirIdx: number, wt: string, role: string) => {
    const overrides = { ...(value[dirIdx].role_overrides ?? {}) };
    if (role) overrides[wt] = role;
    else delete overrides[wt];
    updateField(dirIdx, "role_overrides", overrides);
  };

  // --- work_types ordered list controls ---
  const moveUp = (dirIdx: number, wtIdx: number) => {
    if (wtIdx === 0) return;
    const wts = [...value[dirIdx].work_types];
    [wts[wtIdx - 1], wts[wtIdx]] = [wts[wtIdx], wts[wtIdx - 1]];
    updateField(dirIdx, "work_types", wts);
  };

  const moveDown = (dirIdx: number, wtIdx: number) => {
    const wts = value[dirIdx].work_types;
    if (wtIdx === wts.length - 1) return;
    const next = [...wts];
    [next[wtIdx], next[wtIdx + 1]] = [next[wtIdx + 1], next[wtIdx]];
    updateField(dirIdx, "work_types", next);
  };

  const removeWt = (dirIdx: number, wtIdx: number) => {
    const next = value[dirIdx].work_types.filter((_, j) => j !== wtIdx);
    updateField(dirIdx, "work_types", next);
  };

  const addWt = (dirIdx: number, wt: string) => {
    if (!wt || value[dirIdx].work_types.includes(wt)) return;
    updateField(dirIdx, "work_types", [...value[dirIdx].work_types, wt]);
  };

  const handleAdd = () => {
    onChange([
      ...value,
      {
        name: "",
        labels: [],
        work_types: ["analytics", "development", "code_review", "testing"],
        role_overrides: {},
        designer_id: "",
      },
    ]);
  };

  const handleRemove = (i: number) => {
    onChange(value.filter((_, idx) => idx !== i));
  };

  const workTypeLabel = (wt: string): string => t(`directions.workTypes.${wt}`, { defaultValue: wt });
  const bucketLabel = (bucketKey: string | undefined): string =>
    bucketKey ? t(`directions.buckets.${bucketKey}`) : t("directions.noValue");

  return (
    <div className="space-y-3">
      {value.length === 0 && (
        <p className="text-sm text-gray-400 italic">{t("directions.empty")}</p>
      )}
      {value.map((dir, i) => {
        const available    = ALL_WORK_TYPES.filter((wt) => !dir.work_types.includes(wt));
        const hasDesign    = dir.work_types.includes("design");
        return (
          <div key={i} className="border rounded-lg p-3 bg-gray-50 space-y-2">
            {/* Название + удалить */}
            <div className="flex items-center gap-2">
              <div className="flex-1">
                <label className="block text-xs text-gray-500 mb-0.5">{t("directions.nameLabel")}</label>
                <input
                  type="text"
                  value={dir.name}
                  onChange={(e) => updateField(i, "name", e.target.value)}
                  placeholder={t("directions.namePlaceholder")}
                  className="w-full px-2 py-1 border rounded text-sm"
                />
              </div>
              <button
                onClick={() => handleRemove(i)}
                className="text-red-500 hover:text-red-700 text-xl mt-4 px-1"
                title={t("directions.removeDirection")}
              >
                ×
              </button>
            </div>

            {/* Дизайнер — только если design в pipeline */}
            {hasDesign && designerMembers.length > 1 && (
              <div>
                <label className="block text-xs text-gray-500 mb-0.5">
                  {t("directions.designerLabel")}
                </label>
                <select
                  value={dir.designer_id ?? ""}
                  onChange={(e) => updateField(i, "designer_id", e.target.value)}
                  className="w-full px-2 py-1 border rounded text-sm"
                >
                  <option value="">{t("directions.designerAutoOption")}</option>
                  {designerMembers.map(([accId, m]) => (
                    <option key={accId} value={accId}>
                      {m.file_name || m.jira_name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Метки Jira */}
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">
                {t("directions.labelsLabel")}
              </label>
              <input
                type="text"
                value={dir.labels.join(", ")}
                onChange={(e) =>
                  updateField(
                    i,
                    "labels",
                    e.target.value
                      .split(",")
                      .map((s) => s.trim())
                      .filter(Boolean),
                  )
                }
                placeholder={t("directions.labelsPlaceholder")}
                className="w-full px-2 py-1 border rounded text-sm font-mono"
              />
            </div>

            {/* Pipeline видов работ + роли — единая таблица */}
            <div>
              <label className="block text-xs text-gray-500 mb-1">
                {t("directions.pipelineLabel")}
              </label>
              <p className="text-xs text-gray-400 mb-1">
                {t("directions.pipelineHint")}
              </p>
              <div className="border rounded overflow-hidden bg-white">
                <table className="w-full text-sm">
                  <thead className="bg-gray-100 text-xs text-gray-500">
                    <tr>
                      <th className="text-left px-2 py-1 w-6">#</th>
                      <th className="text-left px-2 py-1">{t("directions.table.workType")}</th>
                      <th className="text-left px-2 py-1">{t("directions.table.bucket")}</th>
                      <th className="text-left px-2 py-1">{t("directions.table.role")}</th>
                      <th className="px-2 py-1 w-20" />
                    </tr>
                  </thead>
                  <tbody>
                    {dir.work_types.map((wt, wi) => {
                      const info = WORK_TYPE_INFO[wt];
                      const overridable = OVERRIDABLE_WORK_TYPES.has(wt);
                      const roleOptions = wt === "development" ? devRoleOptions : contentRoleOptions;
                      const defaultRoleLabel = roleDisplayName(info?.role);
                      return (
                        <tr key={wt} className="border-t">
                          <td className="px-2 py-1 text-gray-400">{wi + 1}</td>
                          <td className="px-2 py-1 font-medium">{workTypeLabel(wt)}</td>
                          <td className="px-2 py-1 text-gray-500">{bucketLabel(info?.bucketKey)}</td>
                          <td className="px-2 py-1">
                            {overridable ? (
                              <select
                                value={dir.role_overrides?.[wt] ?? ""}
                                onChange={(e) => updateOverride(i, wt, e.target.value)}
                                className="w-full px-1.5 py-0.5 border rounded text-sm"
                              >
                                <option value="">
                                  {t("directions.roleDefaultSuffix", { role: defaultRoleLabel })}
                                </option>
                                {roleOptions.map((r) => (
                                  <option key={r.name} value={r.name}>
                                    {r.display_name}
                                  </option>
                                ))}
                              </select>
                            ) : (
                              <span className="text-gray-500">{defaultRoleLabel}</span>
                            )}
                          </td>
                          <td className="px-2 py-1 text-right whitespace-nowrap">
                            <button
                              onClick={() => moveUp(i, wi)}
                              disabled={wi === 0}
                              className="px-1 text-gray-400 hover:text-gray-700 disabled:opacity-20"
                              title={t("directions.moveUp")}
                            >
                              ↑
                            </button>
                            <button
                              onClick={() => moveDown(i, wi)}
                              disabled={wi === dir.work_types.length - 1}
                              className="px-1 text-gray-400 hover:text-gray-700 disabled:opacity-20"
                              title={t("directions.moveDown")}
                            >
                              ↓
                            </button>
                            <button
                              onClick={() => removeWt(i, wi)}
                              className="px-1 text-red-400 hover:text-red-600"
                              title={t("directions.removeStep")}
                            >
                              ×
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {available.length > 0 && (
                <div className="flex items-center gap-2 mt-1">
                  <select
                    className="px-2 py-1 border rounded text-sm"
                    defaultValue=""
                    onChange={(e) => {
                      addWt(i, e.target.value);
                      e.target.value = "";
                    }}
                  >
                    <option value="" disabled>{t("directions.addStepOption")}</option>
                    {available.map((wt) => (
                      <option key={wt} value={wt}>
                        {workTypeLabel(wt)}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>
        );
      })}
      <button
        onClick={handleAdd}
        className="text-sm text-blue-600 hover:text-blue-800"
      >
        {t("directions.addDirection")}
      </button>
    </div>
  );
}
