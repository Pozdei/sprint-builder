import { api } from "./client";
import type { EpicPlanOut, RoadmapGroupBy, RoadmapResponse, TaskDetailOut } from "../types/api";

export async function getRoadmap(groupBy: RoadmapGroupBy): Promise<RoadmapResponse> {
  const r = await api.get("/api/roadmap", { params: { group_by: groupBy } });
  return r.data;
}

export async function setTaskDetail(taskKey: string, detail: string): Promise<TaskDetailOut | null> {
  const r = await api.put("/api/roadmap/task-details", { task_key: taskKey, detail });
  return r.data;
}

export async function getEpicPlans(): Promise<EpicPlanOut[]> {
  const r = await api.get("/api/roadmap/epic-plans");
  return r.data;
}

export async function setEpicPlan(
  epicKey: string, plannedStart: string, plannedEnd: string,
): Promise<EpicPlanOut | null> {
  const r = await api.put("/api/roadmap/epic-plans", {
    epic_key: epicKey, planned_start: plannedStart, planned_end: plannedEnd,
  });
  return r.data;
}
