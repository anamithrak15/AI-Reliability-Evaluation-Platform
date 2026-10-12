export interface ModelSummary {
  model_alias: string;
  scheduled: number;
  executed: number;
  successes: number;
  failures: number;
  skipped: number;
  success_rate: number;
  failure_rate: number;
  quality_score: number | null;
  quality_n: number;
  accuracy: number | null;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  latency_n: number;
  total_input_tokens: number | null;
  total_output_tokens: number | null;
  token_n: number;
  estimated_cost_usd: number | null;
  cost_n: number;
  cost_per_case_usd: number | null;
  cost_complete: boolean;
}

export interface RankedModel {
  model_alias: string;
  eligible: boolean;
  reasons: string[];
  components: Record<string, number>;
  missing_components: string[];
  overall_score: number | null;
  rank: number | null;
}

export interface Comparison {
  run_id: string;
  status: string;
  dataset_name: string | null;
  dataset_version_number: number | null;
  content_hash: string | null;
  evaluation_profile: string | null;
  models: ModelSummary[];
  ranking: {
    models: RankedModel[];
    recommended: string | null;
    explanation: string;
    notes: string[];
    constraints: Record<string, number>;
    weights: Record<string, number>;
  };
}

export interface Finding {
  model_alias: string;
  metric_name: string;
  baseline_value: number | null;
  current_value: number | null;
  delta: number | null;
  severity: "info" | "warning" | "critical";
  explanation: string;
}

export interface Regressions {
  run_id: string;
  baseline_run_id: string | null;
  state: "no_baseline" | "incompatible" | "evaluated";
  incompatibilities: string[];
  thresholds: Record<string, number>;
  findings: Finding[];
  highest_severity: Finding["severity"] | null;
}
