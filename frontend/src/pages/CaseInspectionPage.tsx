import { useCallback } from "react";
import { getCaseDetail } from "../api/runs";
import { StatusBadge } from "../components/RunStatus";
import { Empty, ErrorMessage, Loading } from "../components/StateViews";
import { useApi } from "../hooks/useApi";
import type { CaseResult } from "../types/run";

function Quality({ value }: { value: string | null | undefined }) {
  if (value == null) return <span className="muted">not scored</span>;
  return Number(value) === 1 ? (
    <span className="ok">pass</span>
  ) : (
    <span className="bad">fail ({Number(value).toFixed(2)})</span>
  );
}

function ResultCard({ r }: { r: CaseResult }) {
  return (
    <div className="card">
      <h4>
        {r.model_alias} <StatusBadge status={r.status} />
      </h4>
      <p className="muted">
        {r.latency_ms === null ? "no latency" : `${r.latency_ms} ms`} &middot; tokens {r.input_tokens ?? "-"} /{" "}
        {r.output_tokens ?? "-"} &middot; attempts {r.attempt_count} &middot; quality{" "}
        <Quality value={r.metrics.quality} />
      </p>
      {r.status === "success" ? (
        <pre>{typeof r.output === "string" ? r.output : JSON.stringify(r.output, null, 2)}</pre>
      ) : (
        <p className="bad">
          {r.error_code ?? r.status}
          {r.error_message_redacted ? `: ${r.error_message_redacted}` : ""}
        </p>
      )}
    </div>
  );
}

export default function CaseInspectionPage({ runId, caseKey }: { runId: string; caseKey: string }) {
  const fetcher = useCallback(() => getCaseDetail(runId, caseKey), [runId, caseKey]);
  const { data, error, loading, reload } = useApi(fetcher);

  return (
    <>
      <p>
        <a href={`#/runs/${runId}`}>&larr; Run {runId.slice(0, 8)}</a>
      </p>
      <h1>Case {caseKey}</h1>
      {loading && !data && <Loading what="Loading case" />}
      {error && <ErrorMessage message={error} onRetry={reload} />}
      {data && (
        <>
          <h3>Prompt</h3>
          {data.input.messages.map((m, i) => (
            <p key={i}>
              <strong>{m.role}:</strong> {m.content}
            </p>
          ))}
          <h3>Expectation</h3>
          <p>
            Evaluator: <code>{data.evaluation_config.type}</code>
            {data.tags.length > 0 && <span className="muted"> &middot; tags: {data.tags.join(", ")}</span>}
          </p>
          <pre>{data.expected_output ? JSON.stringify(data.expected_output, null, 2) : "No expected output"}</pre>
          <h3>Model results</h3>
          {data.results.length === 0 && <Empty>No results yet. The run may still be in progress.</Empty>}
          {data.results.some((r) => r.status !== "success") && data.results.length > 0 && (
            <p className="bad">
              {data.results.filter((r) => r.status !== "success").length} of {data.results.length} model results did
              not succeed for this case.
            </p>
          )}
          <div className="grid">
            {data.results.map((r) => (
              <ResultCard key={r.id} r={r} />
            ))}
          </div>
        </>
      )}
    </>
  );
}
