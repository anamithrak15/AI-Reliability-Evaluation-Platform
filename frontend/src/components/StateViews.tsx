import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertIcon, InboxIcon } from "./Icons";

export function Loading({ what = "Loading" }: { what?: string }) {
  return (
    <p role="status" className="loading">
      <span className="spinner" aria-hidden="true" />
      {what}...
    </p>
  );
}

export function ErrorMessage({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="alert-box bad">
      <AlertIcon />
      <p>
        {message}{" "}
        {onRetry && (
          <button className="link" onClick={onRetry}>
            Retry
          </button>
        )}
      </p>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty">
      <InboxIcon size={30} />
      <p>{children}</p>
    </div>
  );
}

interface BoundaryState {
  error: Error | null;
}

/** Keeps one broken page from blanking the whole app. */
export class ErrorBoundary extends Component<{ children: ReactNode }, BoundaryState> {
  state: BoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("render error", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div role="alert" className="card">
          <h3>Something went wrong</h3>
          <p className="bad">{this.state.error.message}</p>
          <p>
            <a href="#/datasets">Back to datasets</a>
          </p>
        </div>
      );
    }
    return this.props.children;
  }
}
