import { useCallback, useEffect, useState } from "react";
import { createDataset, listDatasets } from "../api/datasets";
import ImportForm from "../components/ImportForm";
import PageHeader from "../components/PageHeader";
import { Empty, ErrorMessage, Loading } from "../components/StateViews";
import type { DatasetSummary } from "../types/dataset";

export default function DatasetsPage() {
  const [datasets, setDatasets] = useState<DatasetSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    listDatasets()
      .then((page) => setDatasets(page.items))
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load datasets"));
  }, []);

  useEffect(load, [load]);

  return (
    <>
      <PageHeader title="Datasets" subtitle="Versioned test sets. Every run is scored against an immutable version." />
      {error && <ErrorMessage message={error} onRetry={load} />}
      {!datasets && !error && <Loading what="Loading datasets" />}
      {datasets && datasets.length === 0 && <Empty>No datasets yet. Import one below.</Empty>}
      {datasets && datasets.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Versions</th>
              <th>Latest</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {datasets.map((d) => (
              <tr key={d.id}>
                <td>
                  <a href={`#/datasets/${d.id}`}>{d.name}</a>
                </td>
                <td>{d.version_count}</td>
                <td>{d.latest_version_number ?? "-"}</td>
                <td>{new Date(d.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <ImportForm
        label="Import dataset"
        hint='JSON with "name", optional "description", "schema_version": "1.0" and "cases".'
        onSubmit={async (payload) => {
          await createDataset(payload);
          load();
        }}
      />
    </>
  );
}
