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

// Цвет ячейки бакета — наглядно отделяет анализ от тестирования
function bucketColor(bucket: string): string {
  if (bucket === "Тестирование") return "bg-blue-50 text-blue-800";
  if (bucket === "Анализ") return "bg-amber-50 text-amber-800";
  return "";
}

export function SprintTable({ tasks }: Props) {
  // Описание колонок. В TanStack Table колонка = объект с accessorKey и header.
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
              return (
                <tr
                  key={row.id}
                  className={`border-b hover:bg-gray-50 ${
                    t.partial_from ? "bg-orange-50" : ""
                  }`}
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
