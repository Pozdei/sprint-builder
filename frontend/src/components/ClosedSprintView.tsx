import type { ClosedTaskData, SprintOut, TaskOut } from "../types/api";
import type { IntrusionRecord } from "../types/intrusions";
import { IntrusionsView } from "./IntrusionsView";

interface Props {
  sprint: SprintOut;
}

export function ClosedSprintView({ sprint }: Props) {
  const terminalSet = new Set<string>(
    (sprint.config_snapshot.terminal_statuses as string[] | undefined) ?? [],
  );

  const rows = sprint.tasks.map((task, i) => ({
    task,
    closed: sprint.closed_tasks[i] ?? null,
    done: isDone(task, sprint.closed_tasks[i] ?? null, terminalSet),
  }));

  // Статистика по уникальным Jira-ключам (не по строкам, чтобы не двоить pipeline-задачи)
  const keyMap = new Map<string, { expected: string; done: boolean }>();
  for (const r of rows) {
    if (r.task.is_pseudo) continue;
    const k = r.task.key;
    if (!keyMap.has(k)) {
      keyMap.set(k, {
        expected: r.task.sprint_expected_result ?? "",
        done: r.done,
      });
    } else if (r.done) {
      keyMap.get(k)!.done = true;
    }
  }
  const totalKeys = keyMap.size;
  const doneKeys = Array.from(keyMap.values()).filter((v) => v.done).length;
  const metExpectation = Array.from(keyMap.values()).filter(
    (v) => terminalSet.has(v.expected) && v.done,
  ).length;
  const exceeded = Array.from(keyMap.values()).filter(
    (v) => !terminalSet.has(v.expected) && v.done,
  ).length;

  const totalHours = rows.reduce((sum, r) => sum + r.task.hours, 0);
  const doneHours = rows
    .filter((r) => r.done)
    .reduce((sum, r) => sum + r.task.hours, 0);

  const byOwner = new Map<
    string,
    { file_name: string; total: number; done: number; hours: number; doneHours: number }
  >();
  for (const r of rows) {
    const acc = r.task.owner_id;
    if (!byOwner.has(acc)) {
      byOwner.set(acc, {
        file_name: r.task.owner_file_name,
        total: 0,
        done: 0,
        hours: 0,
        doneHours: 0,
      });
    }
    const s = byOwner.get(acc)!;
    s.total += 1;
    s.hours += r.task.hours;
    if (r.done) {
      s.done += 1;
      s.doneHours += r.task.hours;
    }
  }

  const intrusions = (sprint.intrusions ?? []) as IntrusionRecord[];
  const terminalStatuses =
    (sprint.config_snapshot.terminal_statuses as string[] | undefined) ?? [];

  return (
    <div className="mt-4">
      <h3 className="font-semibold text-gray-700 mb-2">Итоги закрытия</h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <MetricCard
          title="Задач выполнено"
          value={`${doneKeys} из ${totalKeys}`}
          percent={totalKeys ? (doneKeys / totalKeys) * 100 : 0}
        />
        <MetricCard
          title="По плану (ожид. → факт: ✓)"
          value={`${metExpectation} из ${totalKeys}`}
          percent={totalKeys ? (metExpectation / totalKeys) * 100 : 0}
        />
        <MetricCard
          title="Перевыполнено"
          value={String(exceeded)}
          percent={totalKeys ? (exceeded / totalKeys) * 100 : 0}
        />
        <MetricCard
          title="Часов выполнено"
          value={`${doneHours.toFixed(1)} из ${totalHours.toFixed(1)} ч`}
          percent={totalHours ? (doneHours / totalHours) * 100 : 0}
        />
      </div>

      {byOwner.size > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-semibold text-gray-600 mb-2">По людям</h4>
          <table className="w-full text-sm border bg-white">
            <thead className="bg-gray-100">
              <tr>
                <th className="text-left px-3 py-1 border-b">Консультант</th>
                <th className="text-center px-3 py-1 border-b">Задач</th>
                <th className="text-center px-3 py-1 border-b">Часы</th>
                <th className="text-center px-3 py-1 border-b">% задач</th>
                <th className="text-center px-3 py-1 border-b">% часов</th>
              </tr>
            </thead>
            <tbody>
              {Array.from(byOwner.values()).map((s) => (
                <tr key={s.file_name} className="border-b">
                  <td className="px-3 py-1">{s.file_name}</td>
                  <td className="text-center px-3 py-1">
                    {s.done} / {s.total}
                  </td>
                  <td className="text-center px-3 py-1">
                    {s.doneHours.toFixed(1)} / {s.hours.toFixed(1)}
                  </td>
                  <td className="text-center px-3 py-1">
                    {s.total ? ((s.done / s.total) * 100).toFixed(0) : 0}%
                  </td>
                  <td className="text-center px-3 py-1">
                    {s.hours ? ((s.doneHours / s.hours) * 100).toFixed(0) : 0}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h4 className="text-sm font-semibold text-gray-600 mb-2">Было → Стало</h4>
      <div className="border rounded-lg overflow-hidden bg-white">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 border-b">
            <tr>
              <th className="text-left px-3 py-1.5 font-semibold w-10"></th>
              <th className="text-left px-3 py-1.5 font-semibold w-20">Задача</th>
              <th className="text-left px-3 py-1.5 font-semibold">Название</th>
              <th className="text-left px-3 py-1.5 font-semibold">Консультант</th>
              <th className="text-left px-3 py-1.5 font-semibold">Ожид. итог</th>
              <th className="text-left px-3 py-1.5 font-semibold">Было</th>
              <th className="text-left px-3 py-1.5 font-semibold">Стало</th>
              <th className="text-right px-3 py-1.5 font-semibold">Часы</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ task, closed, done }, i) => (
              <tr
                key={`${task.key}-${task.role}-${i}`}
                className={`border-b ${done ? "bg-green-50" : "bg-red-50"}`}
              >
                <td className="text-center px-3 py-1.5">
                  {done ? "✓" : "✗"}
                </td>
                <td className="px-3 py-1.5 font-mono text-xs">
                  {task.is_pseudo ? (
                    <span className="text-gray-400 italic">(псевдо)</span>
                  ) : (
                    <a
                      href={task.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-blue-600 hover:underline"
                    >
                      {task.key}
                    </a>
                  )}
                </td>
                <td
                  className="px-3 py-1.5 max-w-[300px] truncate"
                  title={task.summary}
                >
                  {task.summary}
                </td>
                <td className="px-3 py-1.5 text-gray-700">
                  {task.owner_file_name}
                </td>
                <td className="px-3 py-1.5">
                  {task.is_pseudo ? (
                    <span className="text-gray-400">—</span>
                  ) : task.sprint_expected_result ? (
                    <span className="text-xs font-medium text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded">
                      {task.sprint_expected_result}
                    </span>
                  ) : (
                    <span className="text-gray-400">—</span>
                  )}
                </td>
                <td className="px-3 py-1.5 text-gray-600">
                  {task.is_pseudo ? "—" : task.status_name}
                </td>
                <td className="px-3 py-1.5">
                  {task.is_pseudo ? (
                    <span className="text-gray-400">—</span>
                  ) : closed ? (
                    <span>{closed.status_name}</span>
                  ) : (
                    <span className="text-gray-400 italic">нет данных</span>
                  )}
                </td>
                <td className="text-right px-3 py-1.5 font-semibold">
                  {task.hours.toFixed(1)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <IntrusionsView
        intrusions={intrusions}
        terminalStatuses={terminalStatuses}
      />
    </div>
  );
}

function isDone(task: TaskOut, closed: ClosedTaskData | null,
                 terminalSet: Set<string>): boolean {
  if (task.is_pseudo) return true;
  if (!closed) return false;
  return terminalSet.has(closed.status_name);
}

function MetricCard({ title, value, percent }: {
  title: string;
  value: string;
  percent: number;
}) {
  const color =
    percent >= 80 ? "text-green-700" : percent >= 50 ? "text-yellow-700" : "text-red-700";
  return (
    <div className="border rounded-lg p-3 bg-white shadow-sm">
      <div className="text-xs text-gray-500 uppercase mb-1">{title}</div>
      <div className="flex items-baseline gap-3">
        <div className="text-2xl font-bold text-gray-800">{value}</div>
        <div className={`text-2xl font-bold ${color}`}>
          {percent.toFixed(0)}%
        </div>
      </div>
    </div>
  );
}
