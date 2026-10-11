import { useEffect, useState } from "react";
import { checkHealth, checkReady, type ReadyResponse } from "../api/client";

type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ok"; health: string; ready: ReadyResponse };

export default function StatusPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    Promise.all([checkHealth(), checkReady()])
      .then(([health, ready]) => setState({ kind: "ok", health: health.status, ready }))
      .catch((e: unknown) =>
        setState({ kind: "error", message: e instanceof Error ? e.message : "Unknown error" }),
      );
  }, []);

  return (
    <section>
      <h1>System status</h1>
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
  );
}
