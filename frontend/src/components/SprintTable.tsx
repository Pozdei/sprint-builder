import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import type { TaskOut } from "../types/api";

interface Props {
  tasks: TaskOut[];
  isOverflow?: boolean;
  onEditTask?: (task: TaskOut) => void;
}

function bucketColor(bucket: string): string {
  if (bucket === "Тестирование") return "bg-blue-50 text-blue-800";
  if (bucket === "Анализ") return "bg-amber-50 text-amber-800";
  if (bucket === "Дизайн") return "bg-pink-50 text-pink-800";
  if (bucket === "Дизайн-ревью") return "bg-pink-100 text-pink-900";
  if (bucket === "Разработка") return "bg-green-50 text-green-800";
  if (bucket === "Код-ревью") return "bg-green-100 text-green-900";
  if (bucket === "Руководство") return "bg-purple-50 text-purple-800";
  if (bucket === "Отсутствие") return "bg-gray-100 text-gray-700";
  return "";
}

export function SprintTable({ tasks, isOverflow = false, onEditTask }: Props) {
  const baseColumns: ColumnDef<TaskOut>[] = [
    {
      accessorKey: "priority",
      header: "№",
      cell: (info) => info.getValue() ?? "",
    },
    {
      accessorKey: "key",
      header: "Задача",
      cell: (info) => {
        const t = info.row.original;
        if (t.is_pseudo) {
          return <span className="text-gray-400 italic">(псевдо)</span>;
        }
        return (
          <a
            href={t.url}
            target="_blank"
            rel="noreferrer"
            className="text-blue-600 hover:underline"
          >
            {t.key}
          </a>
        );
      },
    },
    {
      accessorKey: "summary",
      header: "Название",
      cell: (info) => (
        <span className="block max-w-[500px] truncate" title={String(info.getValue())}>
          {String(info.getValue())}
        </span>
      ),
    },
    { accessorKey: "owner_file_name", header: "Исполнитель" },
    {
      accessorKey: "role",
      header: "Роль",
      cell: (info) => {
        const t = info.row.original;
        if (t.is_pseudo) return <span className="text-gray-400">—</span>;
        return <span className="text-xs text-gray-700">{String(info.getValue())}</span>;
      },
    },
    {
      accessorKey: "bucket",
      header: "Фаза",
      cell: (info) => {
        const v = String(info.getValue());
        return <span className={`px-2 py-1 rounded text-xs ${bucketColor(v)}`}>{v}</span>;
      },
    },
    { accessorKey: "status_name", header: "Статус Jira" },
    {
      accessorKey: "sprint_expected_result",
      header: "Ожид. итог",
      cell: (info) => {
        const t = info.row.original;
        if (t.is_pseudo) return null;
        const v = t.sprint_expected_result;
        if (!v) return <span className="text-gray-300">—</span>;
        const isTerminal = !bucketColor(v);
        return (
          <span
            className={`px-2 py-0.5 rounded text-xs font-medium ${
              isTerminal
                ? "bg-emerald-100 text-emerald-800"
                : bucketColor(v) || "bg-gray-100 text-gray-700"
            }`}
          >
            {v}
          </span>
        );
      },
    },
    {
      accessorKey: "hours",
      header: "Часы",
      cell: (info) => {
        const t = info.row.original;
        const hours = Number(info.getValue());

        // Частичная задача: показываем "2.0 из 16 ч"
        if (t.partial_from) {
          return (
            <span className="text-orange-600 font-medium" title="Задача урезана до остатка бюджета">
              {hours.toFixed(1)}{" "}
              <span className="text-orange-400 font-normal">из {t.partial_from} ч</span>
            </span>
          );
        }

        // Дефолтные часы: курсив + серый
        if (t.hours_is_default && !t.is_pseudo) {
          return (
            <span
              className="text-gray-400 italic"
              title="Оценка не задана в Jira — используется дефолт"
            >
              {hours.toFixed(1)}
            </span>
          );
        }

        return <span>{hours.toFixed(1)}</span>;
      },
    },
    {
      id: "hours_analyst",
      header: "Ч. аналит.",
      cell: (info) => {
        const t = info.row.original;
        if (t.is_pseudo) return null;
        const v = t.hours_analyst;
        return v != null
          ? <span className="text-xs">{Number(v).toFixed(1)}</span>
          : <span className="text-xs text-red-300">—</span>;
      },
    },
    {
      id: "hours_tester",
      header: "Ч. тестера",
      cell: (info) => {
        const t = info.row.original;
        if (t.is_pseudo) return null;
        const v = t.hours_tester;
        return v != null
          ? <span className="text-xs">{Number(v).toFixed(1)}</span>
          : <span className="text-xs text-red-300">—</span>;
      },
    },
    {
      id: "hours_developer",
      header: "Ч. разраб.",
      cell: (info) => {
        const t = info.row.original;
        if (t.is_pseudo) return null;
        const v = t.hours_developer;
        return v != null
          ? <span className="text-xs">{Number(v).toFixed(1)}</span>
          : <span className="text-xs text-red-300">—</span>;
      },
    },
    {
      id: "developer_name",
      header: "Разработчик",
      cell: (info) => {
        const t = info.row.original;
        if (t.is_pseudo) return null;
        return t.developer_name
          ? <span className="text-xs">{t.developer_name}</span>
          : <span className="text-xs text-amber-400">—</span>;
      },
    },
    {
      accessorKey: "sprint_name",
      header: "Спринт",
      cell: (info) => info.getValue() || "—",
    },
    { accessorKey: "board", header: "Источник" },
  ];

  const editColumn: ColumnDef<TaskOut> = {
    id: "edit",
    header: "",
    cell: (info) => {
      const t = info.row.original;
      if (t.is_pseudo || !onEditTask) return null;
      return (
        <button
          onClick={() => onEditTask(t)}
          className="text-gray-400 hover:text-blue-600 text-base px-1"
          title="Редактировать в Jira"
        >
          ✎
        </button>
      );
    },
  };

  const overflowColumn: ColumnDef<TaskOut> = {
    accessorKey: "overflow_reason",
    header: "Причина",
    cell: (info) => {
      const v = info.getValue() as string | null | undefined;
      if (!v) return <span className="text-gray-300">—</span>;
      const color =
        v === "Бюджет исчерпан"
          ? "text-red-600"
          : v === "Низкий приоритет"
          ? "text-yellow-600"
          : "text-orange-600";
      return <span className={`text-xs ${color}`}>{v}</span>;
    },
  };

  const columns = [
    ...(onEditTask ? [editColumn] : []),
    ...baseColumns,
    ...(isOverflow ? [overflowColumn] : []),
  ];

  const table = useReactTable({
    data: tasks,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="border rounded-lg overflow-hidden bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-gray-100 border-b">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((h) => (
                  <th
                    key={h.id}
                    className="px-3 py-2 text-left font-semibold text-gray-700"
                  >
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => {
              const t = row.original;
              const rowClass = t.is_pseudo
                ? "bg-gray-50 italic"
                : t.partial_from
                ? "bg-orange-50"
                : "";
              return (
                <tr
                  key={row.id}
                  className={`border-b hover:bg-gray-50 ${rowClass}`}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-3 py-2">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
