import { request } from "./client";
import type { Page } from "../types/dataset";
import type { CaseResult, EvaluationProfile, ModelInfo, Run } from "../types/run";

export const listModels = () => request<ModelInfo[]>("/api/v1/models");
export const listProfiles = () => request<EvaluationProfile[]>("/api/v1/evaluation-profiles");

export const listRuns = (limit = 50, offset = 0) =>
  request<Page<Run>>(`/api/v1/runs?limit=${limit}&offset=${offset}`);

export const getRun = (id: string) => request<Run>(`/api/v1/runs/${id}`);

export const createRun = (payload: {
  dataset_version_id: string;
  model_aliases: string[];
  evaluation_profile: string;
  max_concurrency: number;
}) =>
  request<Run>("/api/v1/runs", {
    method: "POST",
    body: payload,
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });

export const cancelRun = (id: string) => request<Run>(`/api/v1/runs/${id}/cancel`, { method: "POST" });

export function listResults(
  id: string,
  opts: { model_alias?: string; status?: string; limit: number; offset: number },
) {
  const q = new URLSearchParams({ limit: String(opts.limit), offset: String(opts.offset) });
  if (opts.model_alias) q.set("model_alias", opts.model_alias);
  if (opts.status) q.set("status", opts.status);
  return request<Page<CaseResult>>(`/api/v1/runs/${id}/results?${q}`);
}
