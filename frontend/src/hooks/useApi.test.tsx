import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { useApi } from "./useApi";

describe("useApi", () => {
  it("moves from loading to data", async () => {
    const fetcher = vi.fn().mockResolvedValue("hello");
    const { result } = renderHook(() => useApi(fetcher));
    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.data).toBe("hello"));
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("reports a readable error and keeps no data", async () => {
    const fetcher = vi.fn().mockRejectedValue(new ApiError(404, "run_not_found", "Run not found"));
    const { result } = renderHook(() => useApi(fetcher));
    await waitFor(() => expect(result.current.error).toBe("Run not found"));
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("reload refetches and clears a previous error", async () => {
    const fetcher = vi.fn().mockRejectedValueOnce(new Error("flaky")).mockResolvedValueOnce("ok");
    const { result } = renderHook(() => useApi(fetcher));
    await waitFor(() => expect(result.current.error).toBe("flaky"));
    act(() => result.current.reload());
    await waitFor(() => expect(result.current.data).toBe("ok"));
    expect(result.current.error).toBeNull();
    expect(fetcher).toHaveBeenCalledTimes(2);
  });

  it("ignores a slow response that was superseded by a newer fetcher", async () => {
    let resolveSlow: (v: string) => void = () => {};
    const slow = vi.fn(() => new Promise<string>((r) => (resolveSlow = r)));
    const fast = vi.fn().mockResolvedValue("new");
    const { result, rerender } = renderHook(({ f }) => useApi(f), { initialProps: { f: slow as () => Promise<string> } });
    rerender({ f: fast });
    await waitFor(() => expect(result.current.data).toBe("new"));
    await act(async () => resolveSlow("stale"));
    expect(result.current.data).toBe("new");
  });
});
