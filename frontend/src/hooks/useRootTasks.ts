import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchRootTasks } from "../api/client";
import type { RootTaskOut } from "../types/api";

/**
 * Стартовые задачи (📌 на Ганте) для заданного scope (epic_key или "sprint-N") —
 * общий fetch/refetch для страницы прогноза по эпику и истории спринтов.
 */
export function useRootTasks(scopeKey: string | null | undefined) {
  const [rootTasks, setRootTasks] = useState<RootTaskOut[]>([]);

  const reload = useCallback(() => {
    if (scopeKey == null) {
      setRootTasks([]);
      return;
    }
    fetchRootTasks(scopeKey).then(setRootTasks).catch(() => setRootTasks([]));
  }, [scopeKey]);

  useEffect(() => {
    reload();
  }, [reload]);

  /** owner_id → task_key, для пропа GanttChart.rootTasks. */
  const map = useMemo(
    () => Object.fromEntries(rootTasks.map((r) => [r.owner_id, r.task_key])),
    [rootTasks],
  );

  return { rootTasks, map, reload };
}
