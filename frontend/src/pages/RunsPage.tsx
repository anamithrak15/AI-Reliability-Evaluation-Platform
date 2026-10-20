import { useCallback, useEffect, useRef, useState } from "react";
import { listRuns } from "../api/runs";
import NewRunForm from "../components/NewRunForm";
import { ProgressBar, StatusBadge } from "../components/RunStatus";
import PageHeader from "../components/PageHeader";
import { Empty, ErrorMessage, Loading } from "../components/StateViews";
import { ACTIVE_STATUSES, type Run } from "../types/run";

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const anyActive = useRef(false);

  const load = useCallback(() => {
    listRuns()
      .then((page) => {
        anyActive.current = page.items.some((r) => ACTIVE_STATUSES.includes(r.status));
        setRuns(page.items);
        setError(null);
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load runs"));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(() => anyActive.current && load(), 2000);
    return () => clearInterval(timer);
  }, [load]);

  return (
    <>
      <PageHeader title="Runs" subtitle="Each run scores the selected models on one dataset version." />
      {error && <ErrorMessage message={error} onRetry={load} />}
      {!runs && !error && <Loading what="Loading runs" />}
      {runs && runs.length === 0 && (
        <Empty>No runs yet. Pick a dataset and models below and click Start run; then open the run and use Compare.</Empty>
      )}
      {runs && runs.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Run</th>
              <th>Dataset</th>
              <th>Models</th>
              <th>Status</th>
              <th>Progress</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.id}>
                <td>
                  <a href={`#/runs/${r.id}`}>{r.id.slice(0, 8)}</a>
                </td>
                <td>
                  {r.config.dataset_name} v{r.config.dataset_version_number}
                </td>
                <td>{r.config.model_aliases.join(", ")}</td>
                <td>
                  <StatusBadge status={r.status} />
                </td>
                <td>
                  <ProgressBar run={r} />
                </td>
                <td>{new Date(r.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <NewRunForm />
    </>
  );
}
