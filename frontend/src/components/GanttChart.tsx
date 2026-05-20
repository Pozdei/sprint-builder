import { useMemo, useRef, useState } from "react";
import type { GanttItem } from "../types/api";

interface Props {
  items: GanttItem[];
  startDate: string;        // "YYYY-MM-DD"
  hoursPerDay: number;
  onTaskClick?: (key: string) => void;
}

const BUCKET_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  "Анализ":       { bg: "#fef3c7", text: "#92400e", border: "#d97706" },
  "Разработка":   { bg: "#d1fae5", text: "#065f46", border: "#059669" },
  "Код-ревью":    { bg: "#a7f3d0", text: "#064e3b", border: "#047857" },
  "Тестирование": { bg: "#dbeafe", text: "#1e3a5f", border: "#2563eb" },
  "Дизайн":       { bg: "#fce7f3", text: "#831843", border: "#db2777" },
  "Дизайн-ревью": { bg: "#f5d0fe", text: "#581c87", border: "#a855f7" },
  "Руководство":  { bg: "#ede9fe", text: "#4c1d95", border: "#7c3aed" },
  "Отсутствие":   { bg: "#f3f4f6", text: "#374151", border: "#9ca3af" },
};
const DEFAULT_COLOR = { bg: "#f3f4f6", text: "#374151", border: "#9ca3af" };

const ROW_H      = 36;   // px высота строки
const ROW_GAP    = 4;    // px между строками
const LABEL_W    = 160;  // px ширина колонки с именем
const HOUR_PX    = 12;   // px на рабочий час
const HEADER_H   = 48;   // px высота шапки дат

function bucketColor(bucket: string) {
  return BUCKET_COLORS[bucket] ?? DEFAULT_COLOR;
}

function fmtDate(d: Date): string {
  return d.toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" });
}
function fmtDay(d: Date): string {
  return d.toLocaleDateString("ru-RU", { weekday: "short" });
}

interface Tooltip {
  x: number; y: number;
  item: GanttItem;
}

export function GanttChart({ items, startDate, hoursPerDay, onTaskClick }: Props) {
  const [tooltip, setTooltip] = useState<Tooltip | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const clickTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleBarClick = (item: GanttItem) => {
    if (item.is_pseudo) return;

    if (clickTimerRef.current) {
      // Второй клик раньше таймера — двойной клик → открываем Jira
      clearTimeout(clickTimerRef.current);
      clickTimerRef.current = null;
      if (item.url) window.open(item.url, "_blank");
    } else {
      // Первый клик — ждём второго
      clickTimerRef.current = setTimeout(() => {
        clickTimerRef.current = null;
        // Одиночный клик → выделяем все этапы задачи
        setSelectedKey((prev) => (prev === item.key ? null : item.key));
        if (onTaskClick) onTaskClick(item.key);
      }, 260);
    }
  };

  const dayPx = hoursPerDay * HOUR_PX;

  // Группировка по исполнителю
  const owners = useMemo(() => {
    const order: string[] = [];
    const seen = new Set<string>();
    for (const it of items) {
      if (!seen.has(it.owner_file_name)) {
        order.push(it.owner_file_name);
        seen.add(it.owner_file_name);
      }
    }
    return order;
  }, [items]);

  const byOwner = useMemo(() => {
    const m: Record<string, GanttItem[]> = {};
    for (const it of items) {
      (m[it.owner_file_name] ??= []).push(it);
    }
    return m;
  }, [items]);

  // Максимальное время (для ширины графика)
  const maxHours = useMemo(
    () => Math.max(hoursPerDay, ...items.map((i) => i.end_hours)),
    [items, hoursPerDay],
  );

  const totalDays = Math.ceil(maxHours / hoursPerDay);
  const chartW    = totalDays * dayPx;
  const svgH      = HEADER_H + owners.length * (ROW_H + ROW_GAP);

  // Даты для шапки
  const startD = new Date(startDate + "T00:00:00");
  const dateLabels = useMemo(() => {
    const labels: { date: Date; x: number; isWeekend: boolean }[] = [];
    let workDay = 0;
    const d = new Date(startD);
    for (let i = 0; labels.length <= totalDays + 2; i++) {
      const cur = new Date(d);
      cur.setDate(d.getDate() + i);
      const isWeekend = cur.getDay() === 0 || cur.getDay() === 6;
      if (!isWeekend) {
        labels.push({ date: cur, x: workDay * dayPx, isWeekend: false });
        workDay++;
      } else {
        labels.push({ date: cur, x: workDay * dayPx, isWeekend: true });
      }
      if (workDay > totalDays + 1) break;
    }
    return labels;
  }, [startDate, totalDays, dayPx]);

  const hoursToX = (h: number) => h * HOUR_PX;
  const ownerY   = (idx: number) => HEADER_H + idx * (ROW_H + ROW_GAP);

  return (
    <div className="relative overflow-x-auto border rounded-lg bg-white shadow-sm">
      <div style={{ display: "flex", minWidth: LABEL_W + chartW + 24 }}>
        {/* Левая колонка: имена */}
        <div
          style={{ width: LABEL_W, minWidth: LABEL_W, flexShrink: 0 }}
          className="sticky left-0 bg-white z-10 border-r"
        >
          {/* Шапка */}
          <div
            style={{ height: HEADER_H }}
            className="border-b flex items-end pb-1 px-3"
          >
            <span className="text-xs font-semibold text-gray-500">Исполнитель</span>
          </div>
          {/* Строки */}
          {owners.map((name) => (
            <div
              key={name}
              style={{ height: ROW_H + ROW_GAP }}
              className="flex items-center px-3 border-b text-sm font-medium text-gray-700 truncate"
              title={name}
            >
              {name}
            </div>
          ))}
        </div>

        {/* SVG-область */}
        <div className="relative flex-1 overflow-x-auto">
          <svg
            width={chartW + 24}
            height={svgH}
            style={{ display: "block" }}
            onClick={() => setSelectedKey(null)}
          >
            {/* Вертикальные линии дней */}
            {dateLabels
              .filter((l) => !l.isWeekend)
              .map((l, i) => (
                <g key={i}>
                  {/* Заливка выходных (следующий если сегодня пятница) */}
                  <line
                    x1={l.x}
                    y1={HEADER_H}
                    x2={l.x}
                    y2={svgH}
                    stroke="#e5e7eb"
                    strokeWidth={1}
                  />
                </g>
              ))}

            {/* Горизонтальные полосы строк */}
            {owners.map((_, rowI) => (
              <rect
                key={rowI}
                x={0}
                y={ownerY(rowI)}
                width={chartW + 24}
                height={ROW_H}
                fill={rowI % 2 === 0 ? "#fafafa" : "#ffffff"}
              />
            ))}

            {/* Шапка с датами */}
            {dateLabels
              .filter((l) => !l.isWeekend)
              .map((l, i) => (
                <g key={i}>
                  <text
                    x={l.x + 4}
                    y={HEADER_H - 26}
                    fontSize={10}
                    fill="#6b7280"
                    fontWeight="600"
                  >
                    {fmtDay(l.date)}
                  </text>
                  <text
                    x={l.x + 4}
                    y={HEADER_H - 12}
                    fontSize={11}
                    fill="#374151"
                    fontWeight="700"
                  >
                    {fmtDate(l.date)}
                  </text>
                </g>
              ))}

            {/* Полоса текущего шага (сейчас — 0h, т.е. левый край) */}
            <line x1={0} y1={0} x2={0} y2={svgH} stroke="#3b82f6" strokeWidth={2} opacity={0.4} />

            {/* Задачи */}
            {owners.map((name, ownerIdx) => {
              const ownerItems = byOwner[name] ?? [];
              return ownerItems.map((item) => {
                const x = hoursToX(item.start_hours);
                const w = Math.max(2, hoursToX(item.end_hours - item.start_hours));
                const y = ownerY(ownerIdx) + 4;
                const h = ROW_H - 8;
                const col = bucketColor(item.bucket);

                const isSelected   = selectedKey === item.key;
                const isDimmed     = selectedKey !== null && !isSelected && !item.is_pseudo;

                return (
                  <g
                    key={`${item.key}-${item.bucket}-${item.start_hours}`}
                    onMouseEnter={(e) => {
                      const svgEl = e.currentTarget.closest("svg")!;
                      const rect = svgEl.getBoundingClientRect();
                      setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, item });
                    }}
                    onMouseLeave={() => setTooltip(null)}
                    style={{ cursor: item.is_pseudo ? "default" : "pointer" }}
                    onClick={(e) => { e.stopPropagation(); handleBarClick(item); }}
                    opacity={isDimmed ? 0.25 : 1}
                  >
                    {/* Обводка выделенных этапов */}
                    {isSelected && (
                      <rect
                        x={x - 3} y={y - 3}
                        width={w + 6} height={h + 6}
                        rx={5}
                        fill="none"
                        stroke="#3b82f6"
                        strokeWidth={2.5}
                        opacity={0.8}
                      />
                    )}
                    <rect
                      x={x} y={y}
                      width={w} height={h}
                      rx={3}
                      fill={col.bg}
                      stroke={isSelected ? "#2563eb" : col.border}
                      strokeWidth={isSelected ? 2 : 1.5}
                    />
                    {w > 40 && (
                      <text
                        x={x + 5}
                        y={y + h / 2 + 4}
                        fontSize={10}
                        fill={col.text}
                        fontWeight={isSelected ? "700" : "600"}
                      >
                        {w > 80 ? `${item.key} · ${item.bucket}` : item.key}
                      </text>
                    )}
                  </g>
                );
              });
            })}
          </svg>

          {/* Тултип */}
          {tooltip && (
            <div
              className="absolute pointer-events-none z-20 bg-gray-900 text-white text-xs rounded-lg p-2.5 shadow-xl max-w-xs"
              style={{
                left: tooltip.x + 12,
                top: tooltip.y - 10,
                transform: tooltip.x > chartW * 0.65 ? "translateX(-110%)" : undefined,
              }}
            >
              <div className="font-bold mb-0.5">{tooltip.item.key}</div>
              <div className="text-gray-300 mb-1 leading-tight">{tooltip.item.summary}</div>
              <div className="flex gap-2 flex-wrap">
                <span
                  className="px-1.5 py-0.5 rounded text-xs font-medium"
                  style={{
                    background: bucketColor(tooltip.item.bucket).bg,
                    color: bucketColor(tooltip.item.bucket).text,
                  }}
                >
                  {tooltip.item.bucket}
                </span>
                <span className="text-gray-300">{tooltip.item.hours.toFixed(1)} ч</span>
              </div>
              <div className="text-gray-400 mt-1 text-xs">
                {new Date(tooltip.item.start).toLocaleString("ru-RU", {
                  day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
                })}
                {" → "}
                {new Date(tooltip.item.end).toLocaleString("ru-RU", {
                  day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
                })}
              </div>
              {!tooltip.item.is_pseudo && (
                <div className="text-gray-500 mt-1.5 text-xs border-t border-gray-700 pt-1.5">
                  клик — все этапы · двойной — Jira
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Легенда */}
      <div className="flex flex-wrap gap-2 px-4 py-2 border-t bg-gray-50 text-xs">
        {Object.entries(BUCKET_COLORS).map(([bucket, col]) => (
          <span
            key={bucket}
            className="flex items-center gap-1 px-2 py-0.5 rounded border"
            style={{ background: col.bg, color: col.text, borderColor: col.border }}
          >
            {bucket}
          </span>
        ))}
      </div>
    </div>
  );
}
