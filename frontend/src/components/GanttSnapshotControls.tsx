import { fmtDateTime } from "../lib/format";
import type { GanttSnapshotDetail, GanttSnapshotSummary } from "../types/api";

interface ControlsProps {
  snapshots: GanttSnapshotSummary[];
  selectedId: number | "current";
  saving: boolean;
  canSave: boolean;
  onSave: () => void;
  onSelect: (value: string) => void;
}

/** Кнопка «Сохранить снимок» + дропдаун «Вид» — общие для истории спринта и прогноза по эпику. */
export function GanttSnapshotControls({
  snapshots, selectedId, saving, canSave, onSave, onSelect,
}: ControlsProps) {
  return (
    <>
      <button
        onClick={onSave}
        disabled={!canSave || saving}
        title="Сохранить текущий расчёт как статичный снимок"
        className="bg-teal-600 hover:bg-teal-700 disabled:bg-gray-300 text-white px-3 py-1.5 rounded-lg text-sm font-medium transition"
      >
        {saving ? "Сохраняю…" : "💾 Сохранить снимок"}
      </button>
      {snapshots.length > 0 && (
        <label className="text-sm text-gray-600 flex items-center gap-1.5">
          Вид:
          <select
            value={String(selectedId)}
            onChange={(e) => onSelect(e.target.value)}
            className="border rounded-lg px-2 py-1.5 text-sm"
          >
            <option value="current">Текущий расчёт</option>
            {snapshots.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label ? `${s.label} · ` : ""}{fmtDateTime(s.captured_at)}
              </option>
            ))}
          </select>
        </label>
      )}
    </>
  );
}

interface BannerProps {
  snapshot: GanttSnapshotDetail | null;
  onDelete: () => void;
  onReturn: () => void;
}

/** Баннер «исторический снимок» с действиями удаления/возврата к текущему расчёту. */
export function GanttSnapshotBanner({ snapshot, onDelete, onReturn }: BannerProps) {
  return (
    <div className="mt-3 flex items-center justify-between bg-amber-50 border border-amber-300 text-amber-800 rounded-lg px-3 py-2 text-sm">
      <span>
        📷 Исторический снимок от{" "}
        {snapshot ? fmtDateTime(snapshot.captured_at) : "…"}
        {snapshot?.label ? ` · ${snapshot.label}` : ""}
      </span>
      <div className="flex items-center gap-3">
        <button onClick={onDelete} className="text-red-700 hover:text-red-900 underline">
          Удалить снимок
        </button>
        <button onClick={onReturn} className="text-indigo-700 hover:text-indigo-900 underline">
          Вернуться к текущему
        </button>
      </div>
    </div>
  );
}
