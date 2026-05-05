import type { OwnerStat } from "../types/api";

interface Props {
  stats: OwnerStat[];
}

export function OwnerStats({ stats }: Props) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
      {stats.map((s) => {
        const pct = (s.used_hours / s.budget) * 100;
        // Цвет полоски: <70% серый, 70-95% жёлтый, ≥95% зелёный, >100% красный
        const fillColor =
          s.used_hours > s.budget
            ? "bg-red-500"
            : pct >= 95
            ? "bg-green-500"
            : pct >= 70
            ? "bg-yellow-500"
            : "bg-gray-400";

        return (
          <div key={s.owner_id} className="border rounded-lg p-3 bg-white shadow-sm">
            <div className="font-semibold text-gray-800">{s.file_name}</div>
            <div className="text-2xl font-bold mt-1">
              {s.used_hours.toFixed(1)}
              <span className="text-base text-gray-400"> / {s.budget} ч</span>
            </div>
            <div className="w-full h-2 bg-gray-200 rounded mt-2 overflow-hidden">
              <div
                className={`h-full ${fillColor} transition-all`}
                style={{ width: `${Math.min(100, pct)}%` }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
