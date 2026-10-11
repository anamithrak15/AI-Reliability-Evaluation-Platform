import { useState } from "react";
import { ApiError } from "../api/client";

interface Props {
  label: string;
  hint: string;
  onSubmit: (parsed: Record<string, unknown>) => Promise<void>;
}

export default function ImportForm({ label, hint, onSubmit }: Props) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [details, setDetails] = useState<{ loc: string; message: string }[]>([]);

  async function handleFile(file: File | undefined) {
    if (file) setText(await file.text());
  }

  async function submit() {
    setError(null);
    setDetails([]);
    let parsed: unknown;
    try {
      parsed = JSON.parse(text);
    } catch {
      setError("Input is not valid JSON.");
      return;
    }
    if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
      setError("JSON must be an object.");
      return;
    }
    setBusy(true);
    try {
      await onSubmit(parsed as Record<string, unknown>);
      setText("");
    } catch (e) {
      if (e instanceof ApiError) {
        setError(`${e.message} (${e.code})`);
        setDetails(e.details);
      } else {
        setError(e instanceof Error ? e.message : "Unknown error");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card">
      <h3>{label}</h3>
      <p className="muted">{hint}</p>
      <input type="file" accept=".json,application/json" onChange={(e) => handleFile(e.target.files?.[0])} />
      <textarea
        rows={10}
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Paste dataset JSON here"
      />
      <button disabled={busy || !text.trim()} onClick={submit}>
        {busy ? "Submitting..." : "Submit"}
      </button>
      {error && <p className="bad">{error}</p>}
      {details.length > 0 && (
        <ul className="bad">
          {details.map((d, i) => (
            <li key={i}>
              <code>{d.loc || "(root)"}</code>: {d.message}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
