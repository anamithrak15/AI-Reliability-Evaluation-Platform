import { useEffect, useState } from "react";
import { checkHealth, checkReady, type ReadyResponse } from "./api/client";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; health: string; ready: ReadyResponse };

export default function App() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    Promise.all([checkHealth(), checkReady()])
      .then(([health, ready]) => setState({ kind: "ok", health: health.status, ready }))
      .catch((e: unknown) =>
        setState({ kind: "error", message: e instanceof Error ? e.message : "Unknown error" }),
      );
  }, []);

  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>Navigation</h2>
        <ul>
          <li>Datasets (Day 2)</li>
          <li>Runs (Day 3)</li>
          <li>Comparisons (Day 5)</li>
        </ul>
      </aside>
      <main>
        <h1>AI Reliability &amp; Evaluation Platform</h1>
        <p className="banner">Demo mode: simulated models, no live provider calls.</p>
        <section>
          <h3>System status</h3>
          {state.kind === "loading" && <p>Checking API...</p>}
          {state.kind === "error" && <p className="bad">API unreachable: {state.message}</p>}
          {state.kind === "ok" && (
            <>
              <p>Health: {state.health}</p>
              <p>Readiness: {state.ready.status}</p>
              <ul>
                {Object.entries(state.ready.checks).map(([name, status]) => (
                  <li key={name} className={status === "ok" ? "good" : "bad"}>
                    {name}: {status}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      </main>
    </div>
  );
}
