import { useToast } from "../Toast";
import type { PseudoTaskOut, TeamMemberOut } from "../../types/api";

interface Props {
  value: PseudoTaskOut[];
  onChange: (next: PseudoTaskOut[]) => void;
  team: Record<string, TeamMemberOut>;
}

export function PseudoTasksEditor({ value, onChange, team }: Props) {
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
      toast.info(
        "Нет сохранённых людей в команде. Сначала добавьте их через «+ Добавить из Jira» и сохраните конфиг."
      );
      return;
    }
    onChange([
      ...value,
      {
        member_id: members[0].id,
        name: "Отпуск",
        bucket: "Отсутствие",
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
          В команде есть новые люди, которые ещё не сохранены. После сохранения
          конфига они появятся в выпадающем списке псевдо-задач.
        </div>
      )}

      <table className="w-full text-sm border">
        <thead className="bg-gray-100">
          <tr>
            <th className="text-left px-2 py-1 border-b font-semibold">Человек</th>
            <th className="text-left px-2 py-1 border-b font-semibold">Название</th>
            <th className="text-left px-2 py-1 border-b font-semibold">Бакет</th>
            <th className="text-left px-2 py-1 border-b font-semibold w-20">Часы</th>
            <th className="text-center px-2 py-1 border-b font-semibold w-24">Recurring</th>
            <th className="text-left px-2 py-1 border-b font-semibold w-32">Спринт №</th>
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
                        (id={pt.member_id}, не найден)
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
                    placeholder="Отсутствие / Руководство / Обучение"
                    className="w-full px-2 py-1 border rounded"
                  />
                </td>
                <td className="px-2 py-1">
                  <input
                    type="number"
                    step="0.5"
                    value={pt.hours}
                    onChange={(e) => update(i, "hours", Number(e.target.value))}
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
                    placeholder="—"
                    onChange={(e) => {
                      const v = e.target.value;
                      update(i, "target_sprint_num", v === "" ? null : Number(v));
                    }}
                    className="w-full px-2 py-1 border rounded"
                    disabled={pt.recurring}
                    title={pt.recurring
                      ? "Для recurring задач номер спринта не используется"
                      : "Номер целевого спринта (если пусто — задача не попадёт в спринт)"}
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
            );
          })}
        </tbody>
      </table>
      <button
        onClick={handleAdd}
        className="mt-2 text-sm text-blue-600 hover:text-blue-800"
      >
        + Добавить
      </button>
      <p className="text-xs text-gray-500 mt-2">
        <b>Recurring</b> — попадает в каждый спринт автоматически (для регулярных задач
        типа стендапов).<br />
        <b>Спринт №</b> — попадает только в спринт с указанным номером (разово, для отпуска).
        Если оба поля пусты — задача не попадёт ни в один спринт.<br />
        «Руководство» для лидов добавляется автоматически — управляется в базовых настройках.
      </p>
    </div>
  );
}
