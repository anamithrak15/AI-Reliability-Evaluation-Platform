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
    headers: body === undefined ? headers : { "Content-Type": "application/json", ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.ok || acceptStatuses.includes(res.status)) {
    return (await res.json()) as T;
  }
  let envelope: { code?: string; message?: string; details?: ErrorDetail[] } = {};
  try {
    envelope = await res.json();
  } catch {
    // non-JSON error body
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
