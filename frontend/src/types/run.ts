export type RunStatus =
  | "queued"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed"
  | "cancelled";

export const ACTIVE_STATUSES: RunStatus[] = ["queued", "running"];

export interface Run {
  id: string;
  dataset_version_id: string;
  status: RunStatus;
  baseline_run_id: string | null;
  config: {
    dataset_name: string;
    dataset_version_number: number;
    model_aliases: string[];
    evaluation_profile: string;
    max_concurrency: number;
    max_cases: number;
    total_pairs: number;
    requested: { max_concurrency: number; max_cases: number };
  };
  progress: { total_pairs: number; completed_pairs: number; by_status: Record<string, number> };
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  error_summary: string | null;
}

export interface CaseResult {
  id: string;
  case_key: string;
  model_alias: string;
  status: "success" | "provider_error" | "timeout" | "invalid_output" | "skipped";
  output: unknown;
  latency_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: string | null;
  error_code: string | null;
  error_message_redacted: string | null;
  attempt_count: number;
  metrics: Record<string, string | null>;
}

export interface ModelInfo {
  alias: string;
  provider: string;
  description: string;
}

export interface EvaluationProfile {
  name: string;
  description: string;
}
