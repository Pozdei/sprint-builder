import { useState } from "react";
import { deleteEpicSnapshot, pinEpicSnapshot } from "../api/client";
import { fmtDateLong, fmtDateShort } from "../lib/format";
import type { EpicForecastSnapshot } from "../types/api";

interface Props {
  snapshots: EpicForecastSnapshot[];
  onDeleted: (id: number) => void;
  onPinToggled?: (updated: EpicForecastSnapshot) => void;
}

function parseDate(iso: string): number {
  return new Date(iso + "T12:00:00").getTime();
}

export function ForecastTrendChart({ snapshots, onDeleted, onPinToggled }: Props) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  const withDate = snapshots.filter((s) => s.completion_date);
  if (withDate.length < 2) return null;

  const W = 560, H = 100, PAD_X = 8, PAD_Y = 16;
  const plotW = W - PAD_X * 2;
  const plotH = H - PAD_Y * 2;

  const xDates = withDate.map((s) => parseDate(s.captured_date));
  const yDates = withDate.map((s) => parseDate(s.completion_date!));

  const xMin = Math.min(...xDates);
  const xMax = Math.max(...xDates);
  const yMin = Math.min(...yDates);
  const yMax = Math.max(...yDates);

  const xRange = xMax - xMin || 1;
  const yRange = yMax - yMin || 1;

  const px = (ts: number) => PAD_X + ((ts - xMin) / xRange) * plotW;
  const py = (ts: number) => PAD_Y + plotH - ((ts - yMin) / yRange) * plotH;

  const points = withDate.map((s) => ({
    s,
    x: px(parseDate(s.captured_date)),
    y: py(parseDate(s.completion_date!)),
  }));

  const polyline = points.map((p) => `${p.x},${p.y}`).join(" ");

  const first = yDates[0];
  const last = yDates[yDates.length - 1];
  const trending = last > first ? "later" : last < first ? "earlier" : "flat";
  const lineColor = trending === "later" ? "#ef4444" : trending === "earlier" ? "#22c55e" : "#6b7280";

  const handleDelete = async (id: number) => {
    setBusyId(id);
    try {
      await deleteEpicSnapshot(id);
      onDeleted(id);
      setHoveredId(null);
    } finally {
      setBusyId(null);
    }
  };

  const handlePin = async (s: EpicForecastSnapshot) => {
    setBusyId(s.id);
    try {
      const updated = await pinEpicSnapshot(s.id, !s.is_pinned);
      onPinToggled?.(updated);
      setHoveredId(null);
    } finally {
      setBusyId(null);
    }
  };

  const hovered = hoveredId != null ? points.find((p) => p.s.id === hoveredId) : null;

  return (
    <div className="mt-6 bg-white rounded-xl border shadow-sm p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700">Тренд прогноза завершения</h3>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">📌 — закреплённый снапшот</span>
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            trending === "later"   ? "bg-red-50 text-red-600" :
            trending === "earlier" ? "bg-green-50 text-green-600" :
                                     "bg-gray-100 text-gray-500"
          }`}>
            {trending === "later" ? "сдвигается вправо" : trending === "earlier" ? "сдвигается влево" : "стабильно"}
          </span>
        </div>
      </div>

      <div className="relative">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          className="w-full"
          style={{ height: 100 }}
          onMouseLeave={() => setHoveredId(null)}
        >
          {/* Y-grid lines */}
          {[0, 0.5, 1].map((t) => (
            <line
              key={t}
              x1={PAD_X} y1={PAD_Y + plotH * (1 - t)}
              x2={W - PAD_X} y2={PAD_Y + plotH * (1 - t)}
              stroke="#f3f4f6" strokeWidth={1}
            />
          ))}

          {/* Trend line */}
          <polyline
            points={polyline}
            fill="none"
            stroke={lineColor}
            strokeWidth={2}
            strokeLinejoin="round"
          />

          {/* Dots */}
          {points.map(({ s, x, y }) => (
            <g key={s.id}>
              <circle
                cx={x} cy={y} r={hoveredId === s.id ? 5 : 3.5}
                fill={s.is_pinned ? lineColor : (hoveredId === s.id ? lineColor : "white")}
                stroke={s.is_pinned ? "#7c3aed" : lineColor}
                strokeWidth={s.is_pinned ? 2.5 : 2}
                style={{ cursor: "pointer" }}
                onMouseEnter={() => setHoveredId(s.id)}
              />
              {s.is_pinned && (
                <text x={x - 5} y={y - 7} fontSize={9} textAnchor="middle" fill="#7c3aed">📌</text>
              )}
            </g>
          ))}
        </svg>

        {/* Tooltip — pointer-events-auto чтобы кнопки внутри работали */}
        {hovered && (
          <div
            className="absolute z-10 bg-white border rounded-lg shadow-lg p-2.5 text-xs"
            style={{
              left: Math.min(hovered.x / W * 100, 70) + "%",
              top: hovered.y < 40 ? "40%" : "0",
              transform: "translateX(-50%)",
              minWidth: 170,
              pointerEvents: "auto",
            }}
            onMouseEnter={() => setHoveredId(hovered.s.id)}
            onMouseLeave={() => setHoveredId(null)}
          >
            <div className="font-semibold text-gray-700 mb-1 flex items-center gap-1">
              {hovered.s.is_pinned && <span title="Закреплён">📌</span>}
              {fmtDateShort(hovered.s.captured_date)}
            </div>
            <div className="text-gray-600">
              Прогноз: <span className="font-medium">{fmtDateLong(hovered.s.completion_date!)}</span>
            </div>
            <div className="text-gray-400 mt-1">
              {hovered.s.done_issues}/{hovered.s.total_issues} задач выполнено
            </div>
            <div className="flex gap-2 mt-1.5 pt-1.5 border-t border-gray-100">
              <button
                className={`text-xs font-medium disabled:opacity-40 ${
                  hovered.s.is_pinned
                    ? "text-purple-500 hover:text-purple-700"
                    : "text-gray-400 hover:text-purple-600"
                }`}
                disabled={busyId === hovered.s.id}
                onClick={() => handlePin(hovered.s)}
                title={hovered.s.is_pinned ? "Открепить (снапшот будет перезаписываться)" : "Закрепить (не будет перезаписываться)"}
              >
                {busyId === hovered.s.id ? "…" : hovered.s.is_pinned ? "📌 Открепить" : "📌 Закрепить"}
              </button>
              <button
                className="text-xs text-red-400 hover:text-red-600 disabled:opacity-40 ml-auto"
                disabled={busyId === hovered.s.id || hovered.s.is_pinned}
                title={hovered.s.is_pinned ? "Открепите снапшот перед удалением" : "Удалить"}
                onClick={() => handleDelete(hovered.s.id)}
              >
                {busyId === hovered.s.id ? "…" : "Удалить"}
              </button>
            </div>
          </div>
        )}
      </div>

      {/* X-axis labels */}
      <div className="flex justify-between mt-1 px-1">
        <span className="text-xs text-gray-400">{fmtDateShort(withDate[0].captured_date)}</span>
        <span className="text-xs text-gray-400">{fmtDateShort(withDate[withDate.length - 1].captured_date)}</span>
      </div>
    </div>
  );
}
