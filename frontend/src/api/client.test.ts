import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, describeError, request, UNAUTHORIZED_EVENT } from "./client";

function respond(status: number, body: unknown, raw = false) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(raw ? (body as string) : JSON.stringify(body), { status }),
  );
}

afterEach(() => vi.restoreAllMocks());

describe("request", () => {
  it("returns parsed JSON and always sends the CSRF header", async () => {
    const spy = respond(200, { ok: true });
    expect(await request("/x")).toEqual({ ok: true });
    expect(spy.mock.calls[0][1]?.body).toBeUndefined();
    expect(spy.mock.calls[0][1]?.headers).toEqual({ "X-Requested-With": "fetch" });
  });

  it("sends JSON bodies with a content type", async () => {
    const spy = respond(202, {});
    await request("/x", { method: "POST", body: { a: 1 }, headers: { "Idempotency-Key": "k" } });
    const init = spy.mock.calls[0][1]!;
    expect(init.body).toBe('{"a":1}');
    expect(init.headers).toEqual({
      "X-Requested-With": "fetch",
      "Content-Type": "application/json",
      "Idempotency-Key": "k",
    });
  });

  it("accepts empty 204 responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
    await expect(request("/api/v1/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });

  it("announces a lost session on 401 for data calls only", async () => {
    const heard = vi.fn();
    window.addEventListener(UNAUTHORIZED_EVENT, heard);
    try {
      respond(401, { code: "not_authenticated", message: "Sign in to continue" });
      await expect(request("/api/v1/runs")).rejects.toMatchObject({ status: 401 });
      expect(heard).toHaveBeenCalledTimes(1);

      respond(401, { code: "invalid_credentials", message: "Incorrect email or password" });
      await expect(request("/api/v1/auth/login", { method: "POST", body: {} })).rejects.toMatchObject({
        code: "invalid_credentials",
      });
      expect(heard).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener(UNAUTHORIZED_EVENT, heard);
    }
  });

  it("throws ApiError carrying the server error envelope", async () => {
    respond(409, { code: "incompatible_baseline", message: "nope", details: [{ loc: "a", message: "b" }] });
    const err = await request("/x").catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 409, code: "incompatible_baseline", message: "nope" });
    expect((err as ApiError).details).toEqual([{ loc: "a", message: "b" }]);
  });

  it("explains an unreachable backend when the proxy returns a bodiless 5xx", async () => {
    respond(500, "", true);
    await expect(request("/x")).rejects.toMatchObject({
      status: 500,
      code: "api_unreachable",
      message: expect.stringContaining("Cannot reach the API"),
    });
  });

  it("keeps a generic error for other non-JSON failures", async () => {
    respond(418, "teapot", true);
    await expect(request("/x")).rejects.toMatchObject({
      status: 418,
      code: "http_error",
      message: "Request failed with status 418",
    });
  });

  it("trusts a real server error envelope even on a 5xx", async () => {
    respond(500, { code: "internal_error", message: "Internal server error" });
    await expect(request("/x")).rejects.toMatchObject({ code: "internal_error" });
  });

  it("returns the body for explicitly accepted statuses", async () => {
    respond(503, { status: "degraded" });
    expect(await request("/ready", { acceptStatuses: [503] })).toEqual({ status: "degraded" });
  });
});

describe("describeError", () => {
  it("appends server detail messages", () => {
    const e = new ApiError(409, "c", "Not comparable", [{ loc: "x", message: "content differs" }]);
    expect(describeError(e)).toBe("Not comparable: content differs");
  });

  it("handles plain errors and unknown values", () => {
    expect(describeError(new ApiError(500, "c", "boom"))).toBe("boom");
    expect(describeError(new Error("network down"))).toBe("network down");
    expect(describeError("weird")).toBe("Request failed");
  });
});
