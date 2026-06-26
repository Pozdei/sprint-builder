import { VacationEditorCore, type VacationOwner } from "../VacationEditorCore";
import type { TeamMemberOut } from "../../types/api";

interface Props {
  team: Record<string, TeamMemberOut>;
}

/** Редактор отпусков в настройках конфига. Та же единая таблица EmployeeVacation,
 * что и панель отпусков в Ганте — два места заполнения, один источник данных. */
export function VacationsEditor({ team }: Props) {
  const owners: VacationOwner[] = Object.entries(team)
    .map(([accId, m]) => ({
      owner_id: accId,
      display_name: m.file_name || m.jira_name || accId,
    }))
    .filter((o) => o.owner_id)
    .sort((a, b) => a.display_name.localeCompare(b.display_name, "ru"));

  return (
    <div className="max-w-md">
      <VacationEditorCore owners={owners} />
    </div>
  );
}
