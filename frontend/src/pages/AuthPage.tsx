import { useState, type FormEvent } from "react";
import { describeError } from "../api/client";
import { useAuth } from "../auth/AuthContext";

const MIN_PASSWORD = 10;

export default function AuthPage({ mode, notice }: { mode: "login" | "register"; notice?: string | null }) {
  const { login, register } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const creating = mode === "register";

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (creating && password.length < MIN_PASSWORD) {
      setError(`Choose a password of at least ${MIN_PASSWORD} characters.`);
      return;
    }
    setBusy(true);
    try {
      await (creating ? register : login)(email.trim(), password);
      window.location.hash = "#/datasets";
    } catch (err) {
      setError(describeError(err));
      setBusy(false);
    }
  }

  return (
    <form className="card auth-card" onSubmit={submit} aria-labelledby="auth-title">
      <h1 id="auth-title">{creating ? "Create an account" : "Sign in"}</h1>
      {notice && <p className="banner">{notice}</p>}
      <p>
        <label>
          Email
          <input
            type="email"
            name="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
      </p>
      <p>
        <label>
          Password
          <input
            type="password"
            name="password"
            autoComplete={creating ? "new-password" : "current-password"}
            required
            minLength={creating ? MIN_PASSWORD : undefined}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {creating && <span className="muted">At least {MIN_PASSWORD} characters.</span>}
      </p>
      {error && (
        <p role="alert" className="bad">
          {error}
        </p>
      )}
      <button type="submit" disabled={busy}>
        {busy ? "Please wait..." : creating ? "Create account" : "Sign in"}
      </button>
      <p className="muted">
        {creating ? (
          <>
            Already have an account? <a href="#/login">Sign in</a>
          </>
        ) : (
          <>
            New here? <a href="#/register">Create an account</a>
          </>
        )}
      </p>
    </form>
  );
}
