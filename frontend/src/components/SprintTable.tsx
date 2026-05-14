import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import type { TaskOut } from "../types/api";

interface Props {
  tasks: TaskOut[];
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

export function SprintTable({ tasks }: Props) {
  const columns: ColumnDef<TaskOut>[] = [
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
    { accessorKey: "owner_file_name", header: "Консультант" },
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
      accessorKey: "hours",
      header: "Часы",
      cell: (info) => Number(info.getValue()).toFixed(1),
    },
    {
      accessorKey: "sprint_name",
      header: "Спринт",
      cell: (info) => info.getValue() || "—",
    },
    { accessorKey: "board", header: "Источник" },
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
                  className={`border-b hover:bg-gray-100 ${rowClass}`}
                  title={t.partial_from ? `Переходящая, в Jira ${t.partial_from} ч` : ""}
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
