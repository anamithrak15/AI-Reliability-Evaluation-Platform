import { useEffect, useState } from "react";
import { checkHealth, checkReady, type ReadyResponse } from "../api/client";
import PageHeader from "../components/PageHeader";
import { ErrorMessage, Loading } from "../components/StateViews";

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
      <PageHeader title="System status" subtitle="Live checks of the API and the services it depends on." />
      {state.kind === "loading" && <Loading what="Checking API" />}
      {state.kind === "error" && <ErrorMessage message={`API unreachable: ${state.message}`} />}
      {state.kind === "ok" && (
        <ul className="tiles">
          <li className="tile">
            <span className="tile-label">Health</span>
            <span className={`tile-value ${state.health === "ok" ? "good" : "bad"}`}>
              <span className="dot" aria-hidden="true" />
              {state.health}
            </span>
          </li>
          <li className="tile">
            <span className="tile-label">Readiness</span>
            <span className={`tile-value ${state.ready.status === "ok" ? "good" : "bad"}`}>
              <span className="dot" aria-hidden="true" />
              {state.ready.status}
            </span>
          </li>
          {Object.entries(state.ready.checks).map(([name, status]) => (
            <li key={name} className="tile">
              <span className="tile-label">{name}</span>
              <span className={`tile-value ${status === "ok" ? "good" : "bad"}`}>
                <span className="dot" aria-hidden="true" />
                {status}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
