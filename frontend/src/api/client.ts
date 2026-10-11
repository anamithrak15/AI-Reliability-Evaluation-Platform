export interface HealthResponse {
  status: string;
}

export interface ReadyResponse {
  status: string;
  checks: Record<string, string>;
}

async function getJson<T>(path: string, acceptStatuses: number[] = []): Promise<T> {
  const res = await fetch(path);
  if (!res.ok && !acceptStatuses.includes(res.status)) {
    throw new Error(`Request to ${path} failed with status ${res.status}`);
  }
  return (await res.json()) as T;
}

export const checkHealth = () => getJson<HealthResponse>("/health");
// 503 carries a useful body describing which dependency is down.
export const checkReady = () => getJson<ReadyResponse>("/ready", [503]);
