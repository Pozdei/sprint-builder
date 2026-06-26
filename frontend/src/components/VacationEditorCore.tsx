import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { addVacation, deleteVacation, fetchVacations } from "../api/client";
import { useToast } from "./Toast";
import { extractError } from "../lib/api-error";
import { fmtDateDotted } from "../lib/format";
import type { EmployeeVacation } from "../types/api";

export interface VacationOwner {
  owner_id: string;
  display_name: string;
}

interface Props {
  /** Исполнители для выпадающего списка (из Ганта или из команды конфига). */
  owners: VacationOwner[];
  /** Вызывается после любого изменения — например, чтобы перестроить Гант. */
  onChanged?: () => void;
}

/** Список отпусков сотрудников + форма добавления. Работает напрямую с единой
 * таблицей EmployeeVacation (config-scoped) через configs/vacations API.
 *
 * Один источник логики для двух мест заполнения: панель в Ганте
 * (`VacationPanel`) и раздел настроек (`VacationsEditor`). */
export function VacationEditorCore({ owners, onChanged }: Props) {
  const { t } = useTranslation(["forecast", "common"]);
  const toast = useToast();
  const [vacations, setVacations] = useState<EmployeeVacation[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const [selOwner, setSelOwner] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  useEffect(() => {
    setLoading(true);
    fetchVacations()
      .then(setVacations)
      .catch((e) => toast.error(extractError(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Проверка на пересечение с существующими отпусками того же сотрудника
  const overlapWarning = (() => {
    if (!selOwner || !startDate || !endDate || endDate < startDate) return null;
    const existing = vacations.filter((v) => v.jira_account_id === selOwner);
    const overlap = existing.find((v) => startDate <= v.end_date && endDate >= v.start_date);
    if (!overlap) return null;
    return t("vacationPanel.overlapWarning", {
      start: fmtDateDotted(overlap.start_date),
      end: fmtDateDotted(overlap.end_date),
    });
  })();

  const handleAdd = async () => {
    if (!selOwner || !startDate || !endDate) return;
    if (endDate < startDate) {
      toast.error(t("vacationPanel.toast.endBeforeStart"));
      return;
    }
    const owner = owners.find((o) => o.owner_id === selOwner);
    if (!owner) return;
    setSaving(true);
    try {
      const vac = await addVacation({
        jira_account_id: owner.owner_id,
        display_name: owner.display_name,
        start_date: startDate,
        end_date: endDate,
      });
      setVacations((prev) => [...prev, vac]);
      setStartDate("");
      setEndDate("");
      onChanged?.();
      toast.success(t("vacationPanel.toast.vacationAdded", { name: owner.display_name }));
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    setSaving(true);
    try {
      await deleteVacation(id);
      setVacations((prev) => prev.filter((v) => v.id !== id));
      onChanged?.();
      toast.success(t("vacationPanel.toast.vacationDeleted"));
    } catch (e) {
      toast.error(extractError(e));
    } finally {
      setSaving(false);
    }
  };

  // Группировка отпусков по сотруднику
  const byOwner = vacations.reduce<Record<string, EmployeeVacation[]>>((acc, v) => {
    (acc[v.jira_account_id] ??= []).push(v);
    return acc;
  }, {});

  return (
    <div>
      {/* Список отпусков по сотрудникам */}
      <div className="mb-4">
        {loading ? (
          <div className="text-xs text-gray-400">{t("common:loading")}</div>
        ) : Object.keys(byOwner).length === 0 ? (
          <div className="text-xs text-gray-400 italic">{t("vacationPanel.noVacations")}</div>
        ) : (
          <div className="space-y-3">
            {owners
              .filter((o) => byOwner[o.owner_id]?.length > 0)
              .map((o) => (
                <div key={o.owner_id}>
                  <p className="text-xs font-semibold text-gray-700 mb-1">{o.display_name}</p>
                  <ul className="space-y-1">
                    {byOwner[o.owner_id].map((v) => (
                      <li
                        key={v.id}
                        className="flex items-center justify-between bg-orange-50 border border-orange-200 rounded px-3 py-1"
                      >
                        <span className="text-xs text-gray-700">
                          {fmtDateDotted(v.start_date)}
                          {v.start_date !== v.end_date && ` — ${fmtDateDotted(v.end_date)}`}
                        </span>
                        <button
                          onClick={() => handleDelete(v.id)}
                          disabled={saving}
                          className="text-red-400 hover:text-red-600 text-sm ml-2 disabled:opacity-40"
                          title={t("vacationPanel.removeTitle")}
                        >
                          ×
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
          </div>
        )}
      </div>

      {/* Форма добавления */}
      <div className="border-t pt-4">
        <p className="text-xs font-semibold text-gray-600 mb-2">{t("vacationPanel.addSectionTitle")}</p>
        <div className="space-y-2">
          <div>
            <label className="text-xs text-gray-500 block mb-0.5">{t("vacationPanel.employeeLabel")}</label>
            <select
              value={selOwner}
              onChange={(e) => setSelOwner(e.target.value)}
              className="w-full border rounded px-2 py-1 text-xs"
            >
              <option value="">{t("vacationPanel.selectEmployeeOption")}</option>
              {owners.map((o) => (
                <option key={o.owner_id} value={o.owner_id}>{o.display_name}</option>
              ))}
            </select>
          </div>
          <div className="flex gap-2">
            <div className="flex-1">
              <label className="text-xs text-gray-500 block mb-0.5">{t("vacationPanel.fromLabel")}</label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="w-full border rounded px-2 py-1 text-xs"
              />
            </div>
            <div className="flex-1">
              <label className="text-xs text-gray-500 block mb-0.5">{t("vacationPanel.toLabel")}</label>
              <input
                type="date"
                value={endDate}
                min={startDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="w-full border rounded px-2 py-1 text-xs"
              />
            </div>
          </div>
          {overlapWarning && (
            <div className="bg-amber-50 border border-amber-200 text-amber-700 rounded px-2 py-1 text-xs">
              ⚠ {overlapWarning}
            </div>
          )}
          <button
            onClick={handleAdd}
            disabled={!selOwner || !startDate || !endDate || saving}
            className="w-full bg-orange-600 hover:bg-orange-700 disabled:bg-gray-300 text-white px-3 py-1.5 rounded text-xs font-semibold"
          >
            {saving ? t("vacationPanel.saving") : t("vacationPanel.addVacation")}
          </button>
        </div>
      </div>
    </div>
  );
}
