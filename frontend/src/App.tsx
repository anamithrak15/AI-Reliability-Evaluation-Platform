import { useEffect, useState } from "react";
import { listModels } from "./api/runs";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { ErrorBoundary, Loading } from "./components/StateViews";
import AuthPage from "./pages/AuthPage";
import { AccountPage, ForgotPasswordPage, ResetPasswordPage, VerifyEmailPage } from "./pages/AccountPages";
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

// Emailed links look like #/reset-password?token=...; the token stays in the fragment, never sent to a server.
function splitHash(hash: string): { path: string; token: string } {
  const [path, query = ""] = hash.split("?");
  return { path, token: new URLSearchParams(query).get("token") ?? "" };
}

/** Pages that work without a session; null for any other route. */
function publicPage(hash: string) {
  const { path, token } = splitHash(hash);
  if (path === "#/forgot-password") return <ForgotPasswordPage />;
  if (path === "#/reset-password") return <ResetPasswordPage token={token} />;
  if (path === "#/verify-email") return <VerifyEmailPage token={token} />;
  return null;
}

export function Route({ hash }: { hash: string }) {
  const shared = publicPage(hash);
  if (shared) return shared;
  if (hash === "#/account") return <AccountPage />;
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
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}

export function Shell() {
  const hash = useHash();
  const { state, logout } = useAuth();
  const authPage = hash === "#/login" || hash === "#/register";

  useEffect(() => {
    if (state.status === "authenticated" && authPage) window.location.hash = "#/datasets";
  }, [state.status, authPage]);

  if (state.status === "loading") {
    return (
      <div className="layout">
        <main>
          <Loading what="Loading" />
        </main>
      </div>
    );
  }

  if (state.status === "anonymous") {
    return (
      <div className="layout">
        <main>
          <h2>AI Reliability</h2>
          {publicPage(hash) ?? (
            <AuthPage key={hash} mode={hash === "#/register" ? "register" : "login"} notice={state.notice} />
          )}
        </main>
      </div>
    );
  }

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
            <li>
              <a href="#/account">Account</a>
            </li>
          </ul>
        </nav>
        <p className="muted account">
          Signed in as <strong>{state.user.email}</strong>
        </p>
        <button onClick={() => logout()}>Sign out</button>
      </aside>
      <main>
        <Banner />
        {state.user.email_verified_at === null && (
          <p className="banner">
            Your email address is not verified. <a href="#/account">Resend the verification email</a>.
          </p>
        )}
        <ErrorBoundary key={hash}>{authPage ? <Loading /> : <Route hash={hash} />}</ErrorBoundary>
      </main>
    </div>
  );
}
