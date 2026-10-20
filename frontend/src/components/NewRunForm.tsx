import { useCallback, useEffect, useState } from "react";
import { ApiError, describeError } from "../api/client";
import { listDatasets, listVersions } from "../api/datasets";
import { createRun, listModels, listProfiles } from "../api/runs";
import type { DatasetSummary, VersionSummary } from "../types/dataset";
import type { EvaluationProfile, ModelInfo } from "../types/run";
import { ErrorMessage, Loading } from "./StateViews";

export default function NewRunForm() {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [profiles, setProfiles] = useState<EvaluationProfile[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [versionId, setVersionId] = useState("");
  const [selected, setSelected] = useState<string[]>(["fast-model", "accurate-model"]);
  const [profile, setProfile] = useState("classification-v1");
  const [concurrency, setConcurrency] = useState(3);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const loadOptions = useCallback(() => {
    setLoadError(null);
    Promise.all([listDatasets(), listModels(), listProfiles()])
      .then(([d, m, p]) => {
        setDatasets(d.items);
        setModels(m);
        setProfiles(p);
        if (d.items[0]) setDatasetId(d.items[0].id);
        setLoaded(true);
      })
      .catch((e: unknown) => setLoadError(describeError(e)));
  }, []);

  useEffect(() => {
    loadOptions();
  }, [loadOptions]);

  useEffect(() => {
    if (!datasetId) return;
    listVersions(datasetId)
      .then((vs) => {
        setVersions(vs);
        setVersionId(vs[0]?.id ?? "");
      })
      .catch((e: unknown) => setError(describeError(e)));
  }, [datasetId]);

  const toggle = (alias: string) =>
    setSelected((s) => (s.includes(alias) ? s.filter((a) => a !== alias) : [...s, alias]));

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const run = await createRun({
        dataset_version_id: versionId,
        model_aliases: selected,
        evaluation_profile: profile,
        max_concurrency: concurrency,
      });
      window.location.hash = `#/runs/${run.id}`;
    } catch (e) {
      if (e instanceof ApiError) {
        setError([e.message, ...e.details.map((d) => `${d.loc}: ${d.message}`)].join(" - "));
      } else {
        setError(e instanceof Error ? e.message : "Unknown error");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h3>Start a run</h3>
      {loadError && <ErrorMessage message={loadError} onRetry={loadOptions} />}
      {!loaded && !loadError && <Loading what="Loading options" />}
      {loaded && datasets.length === 0 && <p className="muted">Create a dataset first.</p>}
      {loaded && datasets.length > 0 && (
        <>
          <div className="form-row">
            <label>
              Dataset{" "}
              <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>{" "}
            <label>
              Version{" "}
              <select value={versionId} onChange={(e) => setVersionId(e.target.value)}>
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number} ({v.case_count} cases)
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="model-picks">
            <span className="muted">Models:</span>
            {models.map((m) => (
              <label key={m.alias} title={m.description} className="model-pick">
                <input type="checkbox" checked={selected.includes(m.alias)} onChange={() => toggle(m.alias)} />{" "}
                {m.alias}
              </label>
            ))}
          </div>
          <div className="form-row">
            <label>
              Profile{" "}
              <select value={profile} onChange={(e) => setProfile(e.target.value)}>
                {profiles.map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                  </option>
                ))}
              </select>
            </label>{" "}
            <label>
              Concurrency{" "}
              <input
                type="number"
                min={1}
                max={10}
                value={concurrency}
                onChange={(e) => setConcurrency(Number(e.target.value))}
                style={{ width: "4.5rem" }}
              />
            </label>
          </div>
          <button className="primary" disabled={busy || !versionId || selected.length === 0} onClick={submit}>
            {busy ? "Starting..." : "Start run"}
          </button>
        </>
      )}
      {error && <p className="bad">{error}</p>}
    </div>
  );
}
