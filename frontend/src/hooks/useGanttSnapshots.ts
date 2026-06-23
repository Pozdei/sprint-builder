import { useCallback, useEffect, useState } from "react";
import type { GanttItem, GanttSnapshotDetail, GanttSnapshotSummary } from "../types/api";

/** Набор CRUD-функций снимков Ганта — одинаковая форма для спринта и для эпика прогноза. */
export interface GanttSnapshotApi {
  list: () => Promise<GanttSnapshotSummary[]>;
  create: (
    ganttStart: string, hoursPerDay: number, items: GanttItem[], label?: string,
  ) => Promise<GanttSnapshotSummary>;
  get: (id: number) => Promise<GanttSnapshotDetail>;
  remove: (id: number) => Promise<void>;
}

/**
 * Единый стейт-машин для снимков Ганта: используется и на истории спринтов,
 * и на странице прогноза по эпику — оба места работают с одним и тем же backend-механизмом
 * (таблица sprint_gantt_snapshots), различается только api-обёртка (sprint_id vs epic_key).
 */
export function useGanttSnapshots(api: GanttSnapshotApi, scopeKey: string | number | null | undefined) {
  const [snapshots, setSnapshots] = useState<GanttSnapshotSummary[]>([]);
  const [selectedId, setSelectedId] = useState<number | "current">("current");
  const [detail, setDetail] = useState<GanttSnapshotDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const reload = useCallback(() => {
    if (scopeKey == null) {
      setSnapshots([]);
      return;
    }
    api.list().then(setSnapshots).catch(() => setSnapshots([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeKey]);

  useEffect(() => {
    setSelectedId("current");
    setDetail(null);
    reload();
  }, [reload]);

  const save = useCallback(async (
    ganttStart: string, hoursPerDay: number, items: GanttItem[], label?: string,
  ) => {
    setSaving(true);
    try {
      const summary = await api.create(ganttStart, hoursPerDay, items, label);
      setSnapshots((prev) => [summary, ...prev]);
      return summary;
    } finally {
      setSaving(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeKey]);

  const select = useCallback(async (value: number | "current") => {
    if (value === "current") {
      setSelectedId("current");
      setDetail(null);
      return;
    }
    setSelectedId(value);
    setDetailLoading(true);
    try {
      const d = await api.get(value);
      setDetail(d);
    } catch (e) {
      setSelectedId("current");
      throw e;
    } finally {
      setDetailLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeKey]);

  const remove = useCallback(async (id: number) => {
    await api.remove(id);
    setSnapshots((prev) => prev.filter((s) => s.id !== id));
    setSelectedId((cur) => {
      if (cur === id) {
        setDetail(null);
        return "current";
      }
      return cur;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeKey]);

  return { snapshots, selectedId, detail, detailLoading, saving, save, select, remove, reload };
}
