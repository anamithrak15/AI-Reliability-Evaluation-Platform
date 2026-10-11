import { useEffect, useState } from "react";
import DatasetDetailPage from "./pages/DatasetDetailPage";
import DatasetsPage from "./pages/DatasetsPage";
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

function Route({ hash }: { hash: string }) {
  const detail = hash.match(/^#\/datasets\/([0-9a-fA-F-]{36})$/);
  if (detail) return <DatasetDetailPage key={detail[1]} id={detail[1]} />;
  if (hash === "#/status") return <StatusPage />;
  return <DatasetsPage />;
}

export default function App() {
  const hash = useHash();
  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>AI Reliability</h2>
        <ul>
          <li>
            <a href="#/datasets">Datasets</a>
          </li>
          <li className="muted">Runs (Day 3)</li>
          <li className="muted">Comparisons (Day 5)</li>
          <li>
            <a href="#/status">System status</a>
          </li>
        </ul>
      </aside>
      <main>
        <p className="banner">Demo mode: simulated models, no live provider calls.</p>
        <Route hash={hash} />
      </main>
    </div>
  );
}
