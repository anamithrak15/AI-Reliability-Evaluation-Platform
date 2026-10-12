import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { getComparison, getRegressions, setBaseline } from "../api/comparison";
import { getRun, listRuns } from "../api/runs";
import { StatusBadge } from "../components/RunStatus";
import type { Comparison, Regressions } from "../types/comparison";
import type { Run } from "../types/run";

const fmt = (v: number | null, digits = 2, unit = "") => (v === null ? "-" : `${v.toFixed(digits)}${unit}`);
const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const usd = (v: number | null) => (v === null ? "unavailable" : `$${v.toFixed(6)}`);
const BASELINE_OK = ["completed", "completed_with_errors"];

function describe(e: unknown): string {
  if (e instanceof ApiError && e.details.length) return `${e.message}: ${e.details.map((d) => d.message).join("; ")}`;
  return e instanceof Error ? e.message : "Request failed";
}

export default function ComparisonPage({ id }: { id: string }) {
  const [run, setRun] = useState<Run | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [regressions, setRegressions] = useState<Regressions | null>(null);
  const [candidates, setCandidates] = useState<Run[]>([]);
  const [choice, setChoice] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await getRun(id);
      setRun(r);
      setChoice(r.baseline_run_id ?? "");
      const [c, g, runs] = await Promise.all([getComparison(id), getRegressions(id), listRuns(100)]);
      setComparison(c);
      setRegressions(g);
      setCandidates(runs.items.filter((x) => x.id !== id && BASELINE_OK.includes(x.status)));
      setError(null);
    } catch (e) {
      setError(describe(e));
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function apply(baselineId: string | null) {
    setNotice(null);
    try {
      await setBaseline(id, baselineId);
      await load();
    } catch (e) {
      setNotice(describe(e));
    }
  }

  if (error) {
    return (
      <>
        <p>
          <a href={`#/runs/${id}`}>&larr; Run</a>
        </p>
        <p className="bad">{error}</p>
      </>
    );
  }
  if (!run || !comparison || !regressions) return <p>Loading...</p>;

  const rank = comparison.ranking;
  const baseline = candidates.find((c) => c.id === run.baseline_run_id);

  return (
    <>
      <p>
        <a href={`#/runs/${id}`}>&larr; Run {id.slice(0, 8)}</a>
      </p>
      <h1>
        Comparison <StatusBadge status={run.status} />
      </h1>
      <p>
        {comparison.dataset_name} v{comparison.dataset_version_number} &middot; profile:{" "}
        {comparison.evaluation_profile} &middot; dataset hash <code>{comparison.content_hash?.slice(0, 12)}</code>
      </p>

      <h3>Model summary</h3>
      <table>
        <thead>
          <tr>
            <th>Model</th>
            <th>Executed</th>
            <th>Success</th>
            <th>Failure</th>
            <th>Quality</th>
            <th>Latency p50 / p95</th>
            <th>Tokens in/out</th>
            <th>Est. cost</th>
          </tr>
        </thead>
        <tbody>
          {comparison.models.map((m) => (
            <tr key={m.model_alias}>
              <td>{m.model_alias}</td>
              <td>
                {m.executed}
                {m.skipped > 0 && <span className="muted"> (+{m.skipped} skipped)</span>}
              </td>
              <td>{pct(m.success_rate)}</td>
              <td>{pct(m.failure_rate)}</td>
              <td>
                {fmt(m.quality_score, 3)} <span className="muted">n={m.quality_n}</span>
              </td>
              <td>
                {fmt(m.latency_p50_ms, 0, " ms")} / {fmt(m.latency_p95_ms, 0, " ms")}{" "}
                <span className="muted">n={m.latency_n}</span>
              </td>
              <td>
                {m.total_input_tokens ?? "-"} / {m.total_output_tokens ?? "-"}
              </td>
              <td>
                {usd(m.estimated_cost_usd)}
                {m.estimated_cost_usd !== null && !m.cost_complete && <span className="muted"> (partial)</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">
        Latency uses successful calls only. Unavailable means the provider reported no usage or price; it is never
        counted as zero.
      </p>

      <h3>Recommendation</h3>
      <p>{rank.recommended ? <strong>{rank.recommended}</strong> : <strong>No eligible model</strong>}</p>
      <p>{rank.explanation}</p>
      <table>
        <thead>
          <tr>
            <th>Rank</th>
            <th>Model</th>
            <th>Overall</th>
            <th>Components (0-1)</th>
            <th>Eligibility</th>
          </tr>
        </thead>
        <tbody>
          {rank.models.map((m) => (
            <tr key={m.model_alias}>
              <td>{m.rank ?? "-"}</td>
              <td>{m.model_alias}</td>
              <td>{fmt(m.overall_score, 3)}</td>
              <td>
                {Object.entries(m.components)
                  .map(([k, v]) => `${k} ${v.toFixed(2)}`)
                  .join(", ") || "-"}
                {m.missing_components.length > 0 && (
                  <span className="muted"> (no {m.missing_components.join(", ")})</span>
                )}
              </td>
              <td className={m.eligible ? "ok" : "bad"}>{m.eligible ? "eligible" : m.reasons.join("; ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <details>
        <summary>Constraints and weights</summary>
        <p className="muted">
          Constraints: {Object.entries(rank.constraints).map(([k, v]) => `${k}=${v}`).join(", ")}
          <br />
          Weights: {Object.entries(rank.weights).map(([k, v]) => `${k}=${v}`).join(", ")}
        </p>
      </details>
      <ul className="muted">
        {rank.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>

      <h3>Baseline and regressions</h3>
      <p>
        <label>
          Baseline{" "}
          <select value={choice} onChange={(e) => setChoice(e.target.value)}>
            <option value="">none</option>
            {candidates.map((c) => (
              <option key={c.id} value={c.id}>
                {c.id.slice(0, 8)} - {c.config.model_aliases.join(", ")} ({c.config.dataset_name} v
                {c.config.dataset_version_number})
              </option>
            ))}
          </select>
        </label>{" "}
        <button onClick={() => apply(choice || null)} disabled={choice === (run.baseline_run_id ?? "")}>
          Apply
        </button>
      </p>
      {notice && <p className="bad">{notice}</p>}

      {regressions.state === "no_baseline" && <p className="muted">No baseline selected.</p>}
      {regressions.state === "incompatible" && (
        <p className="bad">Baseline is not comparable: {regressions.incompatibilities.join("; ")}</p>
      )}
      {regressions.state === "evaluated" && (
        <>
          <p>
            Compared with baseline{" "}
            <a href={`#/runs/${regressions.baseline_run_id}`}>{regressions.baseline_run_id?.slice(0, 8)}</a>
            {baseline && ` (${baseline.config.model_aliases.join(", ")})`}:{" "}
            {regressions.findings.length === 0 ? (
              <span className="ok">no regressions detected</span>
            ) : (
              <span className={`sev-${regressions.highest_severity}`}>
                highest severity {regressions.highest_severity}
              </span>
            )}
          </p>
          {regressions.findings.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Severity</th>
                  <th>Model</th>
                  <th>Metric</th>
                  <th>Baseline</th>
                  <th>Current</th>
                  <th>Delta</th>
                  <th>Explanation</th>
                </tr>
              </thead>
              <tbody>
                {regressions.findings.map((f, i) => (
                  <tr key={i}>
                    <td className={`sev-${f.severity}`}>{f.severity}</td>
                    <td>{f.model_alias}</td>
                    <td>{f.metric_name}</td>
                    <td>{fmt(f.baseline_value, 3)}</td>
                    <td>{fmt(f.current_value, 3)}</td>
                    <td>{fmt(f.delta, 3)}</td>
                    <td>{f.explanation}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="muted">
            Thresholds:{" "}
            {Object.entries(regressions.thresholds)
              .map(([k, v]) => `${k}=${v}`)
              .join(", ")}
            . A human should review findings before any promotion decision.
          </p>
        </>
      )}
    </>
  );
}
