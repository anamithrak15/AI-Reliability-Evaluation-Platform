import { request } from "./client";
import type { Comparison, Regressions } from "../types/comparison";
import type { Run } from "../types/run";

export const getComparison = (id: string) => request<Comparison>(`/api/v1/runs/${id}/comparison`);
export const getRegressions = (id: string) => request<Regressions>(`/api/v1/runs/${id}/regressions`);
export const setBaseline = (id: string, baselineRunId: string | null) =>
  request<Run>(`/api/v1/runs/${id}/baseline`, {
    method: "POST",
    body: { baseline_run_id: baselineRunId },
  });
