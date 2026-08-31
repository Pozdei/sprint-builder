import type { RoadmapGroupBy, RoadmapGroupOut, RoadmapGroupStatus, RoadmapTaskOut } from "../types/api";

export interface EpicPlanMap {
  [epicKey: string]: { start: string; end: string };
}

/**
 * Группировка задач по эпику или по ручной «Детализации» — считается на клиенте
 * из уже загруженного списка задач (см. RoadmapTaskOut.epic_key/detail), чтобы
 * переключение группировки и inline-редактирование темы не требовали повторного
 * похода в Jira (построение шкалы на бэке может занимать до минуты).
 *
 * `epicPlans` — ручной план старта/окончания по эпику (см. EpicPlanOut), только
 * для groupBy="epic". Не переопределяет факт — оба значения идут рядом, план и
 * факт показываются на таймлайне одновременно.
 *
 * Зеркалит app.sprint.roadmap.build_roadmap_groups на бэкенде — держать в синхроне.
 */
export function buildRoadmapGroups(
  tasks: RoadmapTaskOut[], groupBy: RoadmapGroupBy, epicPlans: EpicPlanMap = {},
): RoadmapGroupOut[] {
  const groups = new Map<string, { key: string; label: string; boards: Set<string>; children: RoadmapTaskOut[] }>();

  for (const t of tasks) {
    let gkey: string | null;
    let glabel: string;
    if (groupBy === "epic") {
      if (!t.epic_key) continue;
      gkey = t.epic_key;
      glabel = `${t.epic_key} ${t.epic_summary ?? ""}`.trim();
    } else {
      if (!t.detail) continue;
      gkey = t.detail;
      glabel = t.detail;
    }
    let g = groups.get(gkey);
    if (!g) {
      g = { key: gkey, label: glabel, boards: new Set(), children: [] };
      groups.set(gkey, g);
    }
    g.children.push(t);
    t.boards.forEach((b) => g!.boards.add(b));
  }

  const result: RoadmapGroupOut[] = [];
  for (const g of groups.values()) {
    const children = g.children;
    const total = children.length;
    const done = children.filter((c) => c.end).length;
    const inProgress = children.filter((c) => c.start && !c.end).length;
    const notStarted = children.filter((c) => !c.start).length;

    const starts = children.map((c) => c.start).filter(Boolean).sort();
    const start = starts[0] ?? "";

    const fullyDone = total > 0 && inProgress === 0 && notStarted === 0;
    const ends = children.map((c) => c.end).filter(Boolean).sort();
    const end = fullyDone && ends.length ? ends[ends.length - 1] : "";

    let status: RoadmapGroupStatus = "not_started";
    if (start && end) status = "done";
    else if (start) status = "in_progress";

    const plan = groupBy === "epic" ? epicPlans[g.key] : undefined;

    result.push({
      key: g.key,
      label: g.label,
      boards: Array.from(g.boards).sort(),
      total, done, in_progress: inProgress, not_started: notStarted,
      start, end, status,
      planned_start: plan?.start ?? "",
      planned_end: plan?.end ?? "",
    });
  }

  // Позиция на таймлайне — по факту, а если факта ещё нет, по плану (иначе
  // ещё не начатые, но уже запланированные эпики тонут в куче "без даты").
  result.sort((a, b) => {
    const aPos = a.start || a.planned_start;
    const bPos = b.start || b.planned_start;
    if (!aPos && !bPos) return a.key.localeCompare(b.key);
    if (!aPos) return 1;
    if (!bPos) return -1;
    return aPos.localeCompare(bPos) || a.key.localeCompare(b.key);
  });
  return result;
}
