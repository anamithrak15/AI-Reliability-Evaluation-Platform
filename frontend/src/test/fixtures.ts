import type { Comparison, ModelSummary, Regressions } from "../types/comparison";
import type { CaseResult, Run } from "../types/run";

export const RUN_ID = "11111111-1111-4111-8111-111111111111";
export const BASE_ID = "22222222-2222-4222-8222-222222222222";

export function makeRun(over: Partial<Run> = {}): Run {
  return {
    id: RUN_ID,
    dataset_version_id: "33333333-3333-4333-8333-333333333333",
    status: "completed",
    baseline_run_id: null,
    config: {
      dataset_name: "support-tickets",
      dataset_version_number: 1,
      model_aliases: ["fast-model"],
      evaluation_profile: "classification-v1",
      max_concurrency: 3,
      max_cases: 100,
      total_pairs: 6,
      requested: { max_concurrency: 3, max_cases: 100 },
    },
    progress: { total_pairs: 6, completed_pairs: 6, by_status: { success: 6 } },
    created_at: "2026-10-12T10:00:00Z",
    started_at: "2026-10-12T10:00:01Z",
    completed_at: "2026-10-12T10:00:05Z",
    error_summary: null,
    ...over,
  };
}

export function makeSummary(over: Partial<ModelSummary> = {}): ModelSummary {
  return {
    model_alias: "fast-model",
    scheduled: 6,
    executed: 6,
    successes: 6,
    failures: 0,
    skipped: 0,
    success_rate: 1,
    failure_rate: 0,
    quality_score: 0.5,
    quality_n: 6,
    accuracy: 0.5,
    latency_p50_ms: 120,
    latency_p95_ms: 180,
    latency_n: 6,
    total_input_tokens: 168,
    total_output_tokens: 24,
    token_n: 6,
    estimated_cost_usd: null,
    cost_n: 0,
    cost_per_case_usd: null,
    cost_complete: false,
    ...over,
  };
}

export function makeComparison(over: Partial<Comparison> = {}): Comparison {
  return {
    run_id: RUN_ID,
    status: "completed",
    dataset_name: "support-tickets",
    dataset_version_number: 1,
    content_hash: "abcdef0123456789",
    evaluation_profile: "classification-v1",
    models: [makeSummary()],
    ranking: {
      models: [
        {
          model_alias: "fast-model",
          eligible: true,
          reasons: [],
          components: { quality: 0.5, latency: 1 },
          missing_components: ["cost"],
          overall_score: 0.62,
          rank: 1,
        },
      ],
      recommended: "fast-model",
      explanation: "fast-model ranks first with an overall score of 0.620.",
      notes: ["This recommendation applies only to this workload and test dataset."],
      constraints: { min_quality: 0.5 },
      weights: { quality: 0.6 },
    },
    ...over,
  };
}

export function makeRegressions(over: Partial<Regressions> = {}): Regressions {
  return {
    run_id: RUN_ID,
    baseline_run_id: null,
    state: "no_baseline",
    incompatibilities: [],
    thresholds: { quality_drop: 0.03 },
    findings: [],
    highest_severity: null,
    ...over,
  };
}

export function makeResult(over: Partial<CaseResult> = {}): CaseResult {
  return {
    id: "r-" + Math.random().toString(16).slice(2),
    case_key: "billing-001",
    model_alias: "fast-model",
    status: "success",
    output: '{"category": "billing"}',
    latency_ms: 120,
    input_tokens: 28,
    output_tokens: 4,
    estimated_cost_usd: null,
    error_code: null,
    error_message_redacted: null,
    attempt_count: 1,
    metrics: { quality: "1.000000" },
    ...over,
  };
}

export const page = <T,>(items: T[]) => ({ items, total: items.length, limit: 50, offset: 0 });
