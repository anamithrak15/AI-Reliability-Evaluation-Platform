import { useEffect, useState, type FormEvent } from "react";
import {
  changePassword,
  forgotPassword,
  resendVerification,
  resetPassword,
  verifyEmail,
} from "../api/auth";
import { describeError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import PageHeader from "../components/PageHeader";

const MIN_PASSWORD = 10;

/** Drop the emailed token from the address bar and history once it has been read. */
function scrubToken() {
  window.history.replaceState(null, "", window.location.pathname + window.location.search + "#/login");
}

function useBusy() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function run(task: () => Promise<void>) {
    setError(null);
    setBusy(true);
    try {
      await task();
    } catch (e) {
      setError(describeError(e));
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, setError, run };
}

function Failure({ message }: { message: string | null }) {
  return message ? (
    <p role="alert" className="bad">
      {message}
    </p>
  ) : null;
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const { busy, error, run } = useBusy();

  function submit(e: FormEvent) {
    e.preventDefault();
    void run(async () => {
      await forgotPassword(email.trim());
      setSent(true);
    });
  }

  return (
    <form className="card auth-card" onSubmit={submit} aria-labelledby="forgot-title">
      <h1 id="forgot-title">Reset your password</h1>
      {sent ? (
        <p role="status">If an account exists for that address, a reset link is on its way. It expires in 30 minutes.</p>
      ) : (
        <>
          <p>
            <label>
              Email
              <input type="email" name="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </label>
          </p>
          <Failure message={error} />
          <button type="submit" disabled={busy}>
            {busy ? "Please wait..." : "Send reset link"}
          </button>
        </>
      )}
      <p className="muted">
        <a href="#/login">Back to sign in</a>
      </p>
    </form>
  );
}

export function ResetPasswordPage({ token }: { token: string }) {
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const { busy, error, setError, run } = useBusy();

  useEffect(() => {
    if (token) scrubToken();
  }, [token]);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (password.length < MIN_PASSWORD) {
      setError(`Choose a password of at least ${MIN_PASSWORD} characters.`);
      return;
    }
    void run(async () => {
      await resetPassword(token, password);
      setDone(true);
    });
  }

  if (!token) {
    return (
      <div className="card auth-card">
        <h1>Reset link incomplete</h1>
        <p>
          Open the link from your email again, or <a href="#/forgot-password">request a new one</a>.
        </p>
      </div>
    );
  }
  if (done) {
    return (
      <div className="card auth-card">
        <h1>Password updated</h1>
        <p role="status">
          You can now <a href="#/login">sign in</a> with your new password.
        </p>
      </div>
    );
  }
  return (
    <form className="card auth-card" onSubmit={submit} aria-labelledby="reset-title">
      <h1 id="reset-title">Choose a new password</h1>
      <p>
        <label>
          New password
          <input
            type="password"
            name="password"
            autoComplete="new-password"
            required
            minLength={MIN_PASSWORD}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        <span className="muted">At least {MIN_PASSWORD} characters.</span>
      </p>
      <Failure message={error} />
      <button type="submit" disabled={busy}>
        {busy ? "Please wait..." : "Update password"}
      </button>
      <p className="muted">
        Link expired? <a href="#/forgot-password">Request a new one</a>
      </p>
    </form>
  );
}

export function VerifyEmailPage({ token }: { token: string }) {
  const { state, updateUser } = useAuth();
  const [result, setResult] = useState<"working" | "ok" | string>(token ? "working" : "This link is incomplete. Open it from your email again.");

  useEffect(() => {
    if (!token) return;
    let current = true;
    verifyEmail(token)
      .then((user) => {
        if (!current) return;
        updateUser(user);
        setResult("ok");
        window.history.replaceState(null, "", window.location.pathname + window.location.search + "#/verify-email");
      })
      .catch((e: unknown) => current && setResult(describeError(e)));
    return () => {
      current = false;
    };
  }, [token, updateUser]);

  const home = state.status === "authenticated" ? "#/datasets" : "#/login";
  return (
    <div className="card auth-card">
      <h1>Email verification</h1>
      {result === "working" && <p role="status">Verifying...</p>}
      {result === "ok" && (
        <p role="status">
          Your email address is verified. <a href={home}>{state.status === "authenticated" ? "Continue" : "Sign in"}</a>
        </p>
      )}
      {result !== "working" && result !== "ok" && (
        <>
          <Failure message={result} />
          <p className="muted">
            <a href={home}>{state.status === "authenticated" ? "Go to the app" : "Sign in"}</a> to request a new link.
          </p>
        </>
      )}
    </div>
  );
}

export function AccountPage() {
  const { state, updateUser } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [changed, setChanged] = useState(false);
  const [resent, setResent] = useState(false);
  const { busy, error, setError, run } = useBusy();
  const resend = useBusy();

  if (state.status !== "authenticated") return null;
  const user = state.user;

  function submit(e: FormEvent) {
    e.preventDefault();
    setChanged(false);
    if (next.length < MIN_PASSWORD) {
      setError(`Choose a password of at least ${MIN_PASSWORD} characters.`);
      return;
    }
    void run(async () => {
      updateUser(await changePassword(current, next));
      setCurrent("");
      setNext("");
      setChanged(true);
    });
  }

  return (
    <>
      <PageHeader title="Account" subtitle="Your email address and password." />
      <section className="card">
        <h2>Email</h2>
        <p>
          {user.email}{" "}
          {user.email_verified_at === null ? <span className="bad">not verified</span> : <span className="muted">verified</span>}
        </p>
        {user.email_verified_at === null && (
          <>
            <button
              onClick={() =>
                void resend.run(async () => {
                  await resendVerification();
                  setResent(true);
                })
              }
              disabled={resend.busy}
            >
              Resend verification email
            </button>
            {resent && <p role="status">Verification email sent.</p>}
            <Failure message={resend.error} />
          </>
        )}
      </section>
      <form className="card" onSubmit={submit} aria-labelledby="change-title">
        <h2 id="change-title">Change password</h2>
        <p>
          <label>
            Current password
            <input type="password" name="current" autoComplete="current-password" required value={current} onChange={(e) => setCurrent(e.target.value)} />
          </label>
        </p>
        <p>
          <label>
            New password
            <input
              type="password"
              name="new"
              autoComplete="new-password"
              required
              minLength={MIN_PASSWORD}
              value={next}
              onChange={(e) => setNext(e.target.value)}
            />
          </label>
          <span className="muted">At least {MIN_PASSWORD} characters. Other devices are signed out.</span>
        </p>
        <Failure message={error} />
        {changed && <p role="status">Password changed.</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Please wait..." : "Change password"}
        </button>
      </form>
    </>
  );
}
