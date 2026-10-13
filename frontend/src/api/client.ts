export interface ErrorDetail {
  loc: string;
  message: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: ErrorDetail[] = [],
  ) {
    super(message);
  }
}

export interface HealthResponse {
  status: string;
}

export interface ReadyResponse {
  status: string;
  checks: Record<string, string>;
}

export const UNAUTHORIZED_EVENT = "auth:unauthorized";

export async function request<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    headers?: Record<string, string>;
    acceptStatuses?: number[];
  } = {},
): Promise<T> {
  const { method = "GET", body, headers = {}, acceptStatuses = [] } = options;
  const res = await fetch(path, {
    method,
    // The server requires this header on state-changing calls; cross-site pages cannot send it.
    headers: {
      "X-Requested-With": "fetch",
      ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      ...headers,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.ok || acceptStatuses.includes(res.status)) {
    // 204 responses (sign out) have no body.
    return (res.status === 204 ? undefined : await res.json()) as T;
  }
  let envelope: { code?: string; message?: string; details?: ErrorDetail[] } = {};
  try {
    envelope = await res.json();
  } catch {
    // non-JSON error body
  }
  // A 401 from anywhere but the sign-in calls means the session is gone.
  if (res.status === 401 && !path.startsWith("/api/v1/auth/")) {
    window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
  }
  // The dev/preview proxy answers with a bodiless 5xx when the backend is down.
  const unreachable = envelope.message === undefined && res.status >= 500 && res.status <= 504;
  throw new ApiError(
    res.status,
    envelope.code ?? (unreachable ? "api_unreachable" : "http_error"),
    envelope.message ??
      (unreachable
        ? `Cannot reach the API (status ${res.status}). Check that the backend is running, then retry.`
        : `Request failed with status ${res.status}`),
    envelope.details ?? [],
  );
}

export function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    return e.details.length ? `${e.message}: ${e.details.map((d) => d.message).join("; ")}` : e.message;
  }
  return e instanceof Error ? e.message : "Request failed";
}

export const checkHealth = () => request<HealthResponse>("/health");
// 503 carries a useful body describing which dependency is down.
export const checkReady = () => request<ReadyResponse>("/ready", { acceptStatuses: [503] });
