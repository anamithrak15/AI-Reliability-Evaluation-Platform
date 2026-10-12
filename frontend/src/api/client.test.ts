import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, describeError, request } from "./client";

function respond(status: number, body: unknown, raw = false) {
  return vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(raw ? (body as string) : JSON.stringify(body), { status }),
  );
}

afterEach(() => vi.restoreAllMocks());

describe("request", () => {
  it("returns parsed JSON and sends no body headers on GET", async () => {
    const spy = respond(200, { ok: true });
    expect(await request("/x")).toEqual({ ok: true });
    expect(spy.mock.calls[0][1]?.body).toBeUndefined();
    expect(spy.mock.calls[0][1]?.headers).toEqual({});
  });

  it("sends JSON bodies with a content type", async () => {
    const spy = respond(202, {});
    await request("/x", { method: "POST", body: { a: 1 }, headers: { "Idempotency-Key": "k" } });
    const init = spy.mock.calls[0][1]!;
    expect(init.body).toBe('{"a":1}');
    expect(init.headers).toEqual({ "Content-Type": "application/json", "Idempotency-Key": "k" });
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
