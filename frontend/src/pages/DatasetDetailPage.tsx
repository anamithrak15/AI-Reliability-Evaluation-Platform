import { useCallback, useEffect, useState } from "react";
import { createVersion, getDataset, getVersion, listVersions } from "../api/datasets";
import ImportForm from "../components/ImportForm";
import PageHeader, { Crumb } from "../components/PageHeader";
import { ErrorMessage, Loading } from "../components/StateViews";
import type { DatasetSummary, VersionDetail, VersionSummary } from "../types/dataset";

export default function DatasetDetailPage({ id }: { id: string }) {
  const [dataset, setDataset] = useState<DatasetSummary | null>(null);
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [detail, setDetail] = useState<VersionDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    (select?: number) => {
      Promise.all([getDataset(id), listVersions(id)])
        .then(([ds, vs]) => {
          setDataset(ds);
          setVersions(vs);
          setSelected(select ?? vs[0]?.version_number ?? null);
        })
        .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load dataset"));
    },
    [id],
  );

  useEffect(() => load(), [load]);

  useEffect(() => {
    if (selected === null) return;
    setDetail(null);
    getVersion(id, selected)
      .then(setDetail)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : "Failed to load version"));
  }, [id, selected]);

  if (error) return <ErrorMessage message={error} />;
  if (!dataset) return <Loading />;

  return (
    <>
      <Crumb href="#/datasets">All datasets</Crumb>
      <PageHeader title={dataset.name} subtitle={dataset.description ?? undefined} />

      <h3>Versions (immutable)</h3>
      <table>
        <thead>
          <tr>
            <th>Version</th>
            <th>Cases</th>
            <th>Content hash</th>
            <th>Created</th>
          </tr>
        </thead>
        <tbody>
          {versions.map((v) => (
            <tr key={v.id} className={v.version_number === selected ? "selected" : ""}>
              <td>
                <button className="link" onClick={() => setSelected(v.version_number)}>
                  v{v.version_number}
                </button>
              </td>
              <td>{v.case_count}</td>
              <td>
                <code>{v.content_hash.slice(0, 12)}</code>
              </td>
              <td>{new Date(v.created_at).toLocaleString()}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected !== null && <h3>Cases in v{selected}</h3>}
      {!detail && selected !== null && <Loading what="Loading cases" />}
      {detail && (
        <table>
          <thead>
            <tr>
              <th>Key</th>
              <th>Prompt</th>
              <th>Expected</th>
              <th>Evaluator</th>
              <th>Tags</th>
            </tr>
          </thead>
          <tbody>
            {detail.cases.map((c) => (
              <tr key={c.id}>
                <td>{c.case_key}</td>
                <td>{c.input.messages.map((m) => m.content).join(" / ")}</td>
                <td>
                  <code>{c.expected_output ? JSON.stringify(c.expected_output) : "-"}</code>
                </td>
                <td>{c.evaluation_config.type}</td>
                <td>{c.tags.join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <ImportForm
        label="Create new version"
        hint='JSON with "schema_version": "1.0" and "cases". Identical content is rejected.'
        onSubmit={async (payload) => {
          // The dataset name/description belong to the dataset, not the version.
          const { cases, schema_version } = payload;
          const created = await createVersion(id, { schema_version, cases });
          load(created.version_number);
        }}
      />
    </>
  );
}
