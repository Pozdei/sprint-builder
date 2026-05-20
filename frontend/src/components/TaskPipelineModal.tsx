import type { GanttItem } from "../types/api";

interface Props {
  taskKey: string;
  allItems: GanttItem[];   // все элементы Ганта (нужны для группировки по ключу)
  onClose: () => void;
}

const BUCKET_ORDER = [
  "Анализ", "Дизайн", "Разработка", "Код-ревью", "Дизайн-ревью", "Тестирование",
];

const BUCKET_COLORS: Record<string, { dot: string; bg: string; text: string }> = {
  "Анализ":       { dot: "bg-amber-400",   bg: "bg-amber-50",   text: "text-amber-800" },
  "Разработка":   { dot: "bg-green-500",   bg: "bg-green-50",   text: "text-green-800" },
  "Код-ревью":    { dot: "bg-emerald-500", bg: "bg-emerald-50", text: "text-emerald-800" },
  "Тестирование": { dot: "bg-blue-500",    bg: "bg-blue-50",    text: "text-blue-800" },
  "Дизайн":       { dot: "bg-pink-500",    bg: "bg-pink-50",    text: "text-pink-800" },
  "Дизайн-ревью": { dot: "bg-fuchsia-500", bg: "bg-fuchsia-50", text: "text-fuchsia-800" },
};
const DEFAULT_COLOR = { dot: "bg-gray-400", bg: "bg-gray-50", text: "text-gray-700" };

function fmtDT(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString("ru-RU", {
    day: "2-digit", month: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function bucketRank(bucket: string): number {
  const idx = BUCKET_ORDER.indexOf(bucket);
  return idx >= 0 ? idx : 99;
}

export function TaskPipelineModal({ taskKey, allItems, onClose }: Props) {
  // Все этапы этой задачи, отсортированные по порядку pipeline (потом по start_hours)
  const stages = allItems
    .filter((it) => it.key === taskKey)
    .sort((a, b) =>
      bucketRank(a.bucket) !== bucketRank(b.bucket)
        ? bucketRank(a.bucket) - bucketRank(b.bucket)
        : a.start_hours - b.start_hours,
    );

  if (stages.length === 0) return null;

  const first = stages[0];
  const last  = stages[stages.length - 1];
  const totalHours = stages.reduce((s, it) => s + it.hours, 0);
  const direction = first.direction;

  // Дата завершения = конец последнего этапа
  const completionDate = new Date(last.end).toLocaleDateString("ru-RU", {
    day: "2-digit", month: "long", year: "numeric",
  });

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[85vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-5 py-4 border-b flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              {first.url ? (
                <a
                  href={first.url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono font-bold text-blue-600 hover:underline text-base"
                >
                  {taskKey}
                </a>
              ) : (
                <span className="font-mono font-bold text-gray-800 text-base">{taskKey}</span>
              )}
              {direction && (
                <span className="text-xs bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full font-medium">
                  {direction}
                </span>
              )}
            </div>
            <p className="text-sm text-gray-600 mt-0.5 leading-tight">
              {first.summary}
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-xl leading-none flex-none"
          >
            ×
          </button>
        </div>

        {/* Pipeline stages */}
        <div className="flex-1 overflow-y-auto px-5 py-3">
          {/* Timeline line */}
          <div className="relative">
            {/* Vertical connector */}
            {stages.length > 1 && (
              <div
                className="absolute left-[11px] top-4 bottom-4 w-0.5 bg-gray-200"
                aria-hidden
              />
            )}

            <div className="space-y-3">
              {stages.map((stage, i) => {
                const col = BUCKET_COLORS[stage.bucket] ?? DEFAULT_COLOR;
                const isLast = i === stages.length - 1;
                return (
                  <div key={`${stage.bucket}-${stage.start_hours}`} className="flex gap-3">
                    {/* Dot */}
                    <div className="flex-none flex flex-col items-center pt-1">
                      <div className={`w-5 h-5 rounded-full border-2 border-white shadow ${col.dot} z-10`} />
                    </div>

                    {/* Content */}
                    <div className={`flex-1 rounded-xl px-3 py-2.5 ${col.bg} ${isLast ? "ring-1 ring-inset ring-gray-200" : ""}`}>
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <span className={`text-sm font-semibold ${col.text}`}>
                          {stage.bucket}
                        </span>
                        <span className="text-xs font-mono font-medium text-gray-600 bg-white/70 px-1.5 py-0.5 rounded">
                          {stage.hours.toFixed(1)} ч
                        </span>
                      </div>
                      <div className="flex items-center justify-between mt-1 flex-wrap gap-x-3">
                        <span className="text-xs text-gray-600">
                          👤 {stage.owner_file_name}
                        </span>
                        <span className="text-xs text-gray-400 font-mono">
                          {fmtDT(stage.start)} → {fmtDT(stage.end)}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t px-5 py-3 bg-gray-50 rounded-b-2xl flex items-center justify-between">
          <div className="text-sm text-gray-500">
            <span className="font-medium text-gray-700">{stages.length}</span> этапов ·{" "}
            <span className="font-medium text-gray-700">{totalHours.toFixed(1)} ч</span> итого
          </div>
          <div className="text-sm">
            <span className="text-gray-500">Завершение: </span>
            <span className="font-semibold text-gray-800">{completionDate}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
