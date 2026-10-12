import { useEffect, useState } from "react";
import { listModels } from "./api/runs";
import { ErrorBoundary } from "./components/StateViews";
import CaseInspectionPage from "./pages/CaseInspectionPage";
import ComparisonPage from "./pages/ComparisonPage";
import DatasetDetailPage from "./pages/DatasetDetailPage";
import DatasetsPage from "./pages/DatasetsPage";
import RunDetailPage from "./pages/RunDetailPage";
import RunsPage from "./pages/RunsPage";
import StatusPage from "./pages/StatusPage";

function useHash(): string {
  const [hash, setHash] = useState(window.location.hash || "#/datasets");
  useEffect(() => {
    const onChange = () => setHash(window.location.hash || "#/datasets");
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return hash;
}

const UUID = "([0-9a-fA-F-]{36})";

export function Route({ hash }: { hash: string }) {
  const dataset = hash.match(new RegExp(`^#/datasets/${UUID}$`));
  if (dataset) return <DatasetDetailPage key={dataset[1]} id={dataset[1]} />;
  const compare = hash.match(new RegExp(`^#/runs/${UUID}/compare$`));
  if (compare) return <ComparisonPage key={compare[1]} id={compare[1]} />;
  const inspect = hash.match(new RegExp(`^#/runs/${UUID}/cases/([A-Za-z0-9._-]{1,200})$`));
  if (inspect) return <CaseInspectionPage key={hash} runId={inspect[1]} caseKey={inspect[2]} />;
  const run = hash.match(new RegExp(`^#/runs/${UUID}$`));
  if (run) return <RunDetailPage key={run[1]} id={run[1]} />;
  if (hash === "#/runs") return <RunsPage />;
  if (hash === "#/status") return <StatusPage />;
  if (hash === "#/datasets" || hash === "#/" || hash === "#") return <DatasetsPage />;
  return (
    <>
      <h1>Page not found</h1>
      <p>
        There is nothing at <code>{hash}</code>. <a href="#/datasets">Go to datasets</a>.
      </p>
    </>
  );
}

export function Banner() {
  const [live, setLive] = useState<string[]>([]);
  useEffect(() => {
    listModels()
      .then((models) => setLive(models.filter((m) => m.provider !== "mock").map((m) => m.alias)))
      .catch(() => setLive([]));
  }, []);
  return live.length > 0 ? (
    <p className="banner banner-live">Live models enabled: {live.join(", ")}. Mock models are still simulated.</p>
  ) : (
    <p className="banner">Demo mode: simulated models, no live provider calls.</p>
  );
}

export default function App() {
  const hash = useHash();
  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>AI Reliability</h2>
        <nav aria-label="Main">
          <ul>
            <li>
              <a href="#/datasets">Datasets</a>
            </li>
            <li>
              <a href="#/runs">Runs</a>
            </li>
            <li className="muted">Comparisons: open a finished run</li>
            <li>
              <a href="#/status">System status</a>
            </li>
          </ul>
        </nav>
      </aside>
      <main>
        <Banner />
        <ErrorBoundary key={hash}>
          <Route hash={hash} />
        </ErrorBoundary>
      </main>
    </div>
  );
}
