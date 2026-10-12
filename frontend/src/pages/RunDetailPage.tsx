import { useCallback, useEffect, useRef, useState } from "react";
import { cancelRun, getRun, listResults } from "../api/runs";
import { ProgressBar, StatusBadge } from "../components/RunStatus";
import type { Page } from "../types/dataset";
import { ACTIVE_STATUSES, type CaseResult, type Run } from "../types/run";

const PAGE_SIZE = 25;
const RESULT_STATUSES = ["success", "provider_error", "timeout", "skipped"];

export default function RunDetailPage({ id }: { id: string }) {
  const [run, setRun] = useState<Run | null>(null);
  const [results, setResults] = useState<Page<CaseResult> | null>(null);
  const [model, setModel] = useState("");
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const active = useRef(true);

  const load = useCallback(async () => {
    try {
      const r = await getRun(id);
      active.current = ACTIVE_STATUSES.includes(r.status);
      setRun(r);
      setResults(
        await listResults(id, {
          model_alias: model || undefined,
          status: status || undefined,
          limit: PAGE_SIZE,
          offset,
        }),
      );
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load run");
    }
  }, [id, model, status, offset]);

  useEffect(() => {
    load();
    const timer = setInterval(() => active.current && load(), 1500);
    return () => clearInterval(timer);
  }, [load]);

  async function cancel() {
    try {
      setRun(await cancelRun(id));
      active.current = false;
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Cancel failed");
    }
  }

  if (!run) return error ? <p className="bad">{error}</p> : <p>Loading...</p>;

  return (
    <>
      <p>
        <a href="#/runs">&larr; All runs</a>
      </p>
      <h1>
        Run {run.id.slice(0, 8)} <StatusBadge status={run.status} />
      </h1>
      <p>
        {run.config.dataset_name} v{run.config.dataset_version_number} &middot; models:{" "}
        {run.config.model_aliases.join(", ")} &middot; profile: {run.config.evaluation_profile} &middot;
        concurrency: {run.config.max_concurrency}
        {run.config.requested.max_concurrency !== run.config.max_concurrency &&
          ` (requested ${run.config.requested.max_concurrency}, capped by server)`}
      </p>
      <ProgressBar run={run} />
      <p className="muted">
        {Object.entries(run.progress.by_status)
          .map(([k, v]) => `${k}: ${v}`)
          .join(" | ") || "no results yet"}
      </p>
      {run.error_summary && <p className="bad">Issues: {run.error_summary}</p>}
      {ACTIVE_STATUSES.includes(run.status) && <button onClick={cancel}>Cancel run</button>}
      {error && <p className="bad">{error}</p>}

      <h3>Case results</h3>
      <p>
        <label>
          Model{" "}
          <select
            value={model}
            onChange={(e) => {
              setModel(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">all</option>
            {run.config.model_aliases.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </label>{" "}
        <label>
          Status{" "}
          <select
            value={status}
            onChange={(e) => {
              setStatus(e.target.value);
              setOffset(0);
            }}
          >
            <option value="">all</option>
            {RESULT_STATUSES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
      </p>
      {results && results.items.length === 0 && <p className="muted">No results to show.</p>}
      {results && results.items.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Case</th>
              <th>Model</th>
              <th>Status</th>
              <th>Latency</th>
              <th>Tokens in/out</th>
              <th>Attempts</th>
              <th>Quality</th>
              <th>Output / error</th>
            </tr>
          </thead>
          <tbody>
            {results.items.map((r) => (
              <tr key={r.id}>
                <td>{r.case_key}</td>
                <td>{r.model_alias}</td>
                <td>
                  <StatusBadge status={r.status} />
                </td>
                <td>{r.latency_ms === null ? "-" : `${r.latency_ms} ms`}</td>
                <td>
                  {r.input_tokens ?? "-"} / {r.output_tokens ?? "-"}
                </td>
                <td>{r.attempt_count}</td>
                <td>
                  {r.metrics.quality == null ? (
                    "-"
                  ) : Number(r.metrics.quality) === 1 ? (
                    <span className="ok">pass</span>
                  ) : (
                    <span className="bad">fail ({Number(r.metrics.quality).toFixed(2)})</span>
                  )}
                </td>
                <td>
                  {r.status === "success" ? (
                    <code>{String(r.output)}</code>
                  ) : (
                    <span className="bad">
                      {r.error_code}: {r.error_message_redacted}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {results && results.total > PAGE_SIZE && (
        <p>
          <button disabled={offset === 0} onClick={() => setOffset(offset - PAGE_SIZE)}>
            Previous
          </button>{" "}
          {offset + 1}-{Math.min(offset + PAGE_SIZE, results.total)} of {results.total}{" "}
          <button
            disabled={offset + PAGE_SIZE >= results.total}
            onClick={() => setOffset(offset + PAGE_SIZE)}
          >
            Next
          </button>
        </p>
      )}
    </>
  );
}
