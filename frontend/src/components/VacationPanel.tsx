import { useTranslation } from "react-i18next";
import { VacationEditorCore, type VacationOwner } from "./VacationEditorCore";
import type { GanttItem } from "../types/api";

interface Props {
  ganttItems: GanttItem[];
  onClose: () => void;
  onChanged: () => void;  // вызывается после изменения (для перестройки Ганта)
}

export function VacationPanel({ ganttItems, onClose, onChanged }: Props) {
  const { t } = useTranslation(["forecast", "common"]);

  // Уникальные исполнители из Ганта (с owner_id)
  const owners: VacationOwner[] = Array.from(
    new Map(
      ganttItems
        .filter((i) => !i.is_pseudo && i.owner_id)
        .map((i) => [i.owner_id, { owner_id: i.owner_id, display_name: i.owner_file_name || i.owner_id }])
    ).values()
  ).sort((a, b) => (a.display_name || "").localeCompare(b.display_name || "", "ru"));

  return (
    <div className="fixed inset-y-0 right-0 w-80 bg-white border-l shadow-xl z-30 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b bg-gray-50">
        <h2 className="text-sm font-semibold text-gray-800">{t("vacationPanel.title")}</h2>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">×</button>
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        <VacationEditorCore owners={owners} onChanged={onChanged} />
      </div>

      <div className="px-4 py-3 border-t bg-gray-50">
        <p className="text-xs text-gray-400">
          {t("vacationPanel.footerHint")}
        </p>
      </div>
    </div>
  );
}
