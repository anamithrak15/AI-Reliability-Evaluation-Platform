import type { Run } from "../types/run";

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${status}`}>{status.replace(/_/g, " ")}</span>;
}

export function ProgressBar({ run }: { run: Run }) {
  const { completed_pairs: done, total_pairs: total } = run.progress;
  const pct = total === 0 ? 0 : Math.round((done / total) * 100);
  return (
    <div className="progress" title={`${done}/${total}`}>
      <div className="progress-fill" style={{ width: `${pct}%` }} />
      <span>
        {done}/{total}
      </span>
    </div>
  );
}
