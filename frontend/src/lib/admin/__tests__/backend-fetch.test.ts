import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `adminBackendFetch` — the one session-gate-then-relay implementation
 * used by BOTH the read Route Handlers (`route.ts`, `[id]/route.ts`) and
 * the write Server Actions (`actions.ts`) — design.md's "Decision: no
 * write Route Handlers — Server Actions relay directly" centralizes this
 * logic here instead of duplicating the gate in every caller.
 *
 * `createSessionClient` is mocked (per design.md's Testing Strategy:
 * "Stubbed `createSessionClient` + spied `fetch`") so this proves the
 * auth gate and relay logic in isolation, without a live Supabase or
 * FastAPI. `getClaims()` gates; `fetch` MUST NEVER be called without
 * claims — the same "never reaches the repository" posture `route.ts`
 * already proves for the GET-only case.
 *
 * @see design.md "Frontend relay"
 */

const GET_CLAIMS = vi.fn();
const GET_SESSION = vi.fn();

vi.mock("@/lib/supabase/server", () => ({
  createSessionClient: vi.fn(async () => ({
    auth: {
      getClaims: GET_CLAIMS,
      getSession: GET_SESSION,
    },
  })),
}));

vi.mock("@/lib/admin/env", () => ({
  getBackendUrl: () => "http://127.0.0.1:8000",
}));

async function importBackendFetch() {
  const mod = await import("../backend-fetch");
  return mod.adminBackendFetch;
}

describe("adminBackendFetch", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("returns unauthenticated and never calls fetch when there are no claims", async () => {
    GET_CLAIMS.mockResolvedValue({
      data: null,
      error: { message: "invalid_token" },
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const adminBackendFetch = await importBackendFetch();
    const result = await adminBackendFetch("/admin/products");

    expect(result).toEqual({ outcome: "unauthenticated" });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("returns unauthenticated and never calls fetch when claims are empty", async () => {
    GET_CLAIMS.mockResolvedValue({ data: { claims: null }, error: null });
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const adminBackendFetch = await importBackendFetch();
    const result = await adminBackendFetch("/admin/products");

    expect(result).toEqual({ outcome: "unauthenticated" });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("relays method, JSON body, and the Bearer token when claims are present", async () => {
    GET_CLAIMS.mockResolvedValue({
      data: { claims: { sub: "admin-1" } },
      error: null,
    });
    GET_SESSION.mockResolvedValue({
      data: { session: { access_token: "real-jwt-token" } },
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      status: 201,
      json: () => Promise.resolve({ id: "p1" }),
    } as Response);

    const adminBackendFetch = await importBackendFetch();
    const result = await adminBackendFetch("/admin/products", {
      method: "POST",
      body: { name: "Funda iPhone 15" },
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [requestUrl, requestInit] = fetchSpy.mock.calls[0];
    expect(String(requestUrl)).toBe("http://127.0.0.1:8000/admin/products");
    const init = requestInit as RequestInit;
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ name: "Funda iPhone 15" }));
    expect(init.headers).toMatchObject({
      Authorization: "Bearer real-jwt-token",
      "Content-Type": "application/json",
    });

    expect(result).toEqual({
      outcome: "response",
      status: 201,
      body: { id: "p1" },
    });
  });

  it("returns body: null for a 204 response without calling .json()", async () => {
    GET_CLAIMS.mockResolvedValue({
      data: { claims: { sub: "admin-1" } },
      error: null,
    });
    GET_SESSION.mockResolvedValue({
      data: { session: { access_token: "real-jwt-token" } },
    });
    const jsonSpy = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      status: 204,
      json: jsonSpy,
    } as unknown as Response);

    const adminBackendFetch = await importBackendFetch();
    const result = await adminBackendFetch("/admin/products/p1", {
      method: "DELETE",
    });

    expect(jsonSpy).not.toHaveBeenCalled();
    expect(result).toEqual({ outcome: "response", status: 204, body: null });
  });

  it("relays a FormData body directly — no JSON.stringify, no Content-Type header (design.md Decision 8)", async () => {
    GET_CLAIMS.mockResolvedValue({
      data: { claims: { sub: "admin-1" } },
      error: null,
    });
    GET_SESSION.mockResolvedValue({
      data: { session: { access_token: "real-jwt-token" } },
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      status: 201,
      json: () => Promise.resolve({ id: "img1" }),
    } as Response);

    const formData = new FormData();
    formData.set("file", new File(["binary"], "photo.webp"));

    const adminBackendFetch = await importBackendFetch();
    await adminBackendFetch("/admin/products/p1/images", {
      method: "POST",
      body: formData,
    });

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, requestInit] = fetchSpy.mock.calls[0];
    const init = requestInit as RequestInit;

    // The exact same FormData instance must reach `fetch` — never
    // `JSON.stringify`'d (which would silently produce `"[object
    // FormData]"` and corrupt the multipart upload).
    expect(init.body).toBe(formData);

    // Setting a manual `Content-Type` here would omit the `boundary=`
    // parameter FastAPI's multipart parser requires (design.md Decision
    // 8) — the browser/undici must set it instead.
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer real-jwt-token");
    expect(headers["Content-Type"]).toBeUndefined();
  });

  it("still JSON.stringifies and sets Content-Type for a plain object body (regression)", async () => {
    GET_CLAIMS.mockResolvedValue({
      data: { claims: { sub: "admin-1" } },
      error: null,
    });
    GET_SESSION.mockResolvedValue({
      data: { session: { access_token: "real-jwt-token" } },
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      status: 200,
      json: () => Promise.resolve({ id: "p1" }),
    } as Response);

    const adminBackendFetch = await importBackendFetch();
    await adminBackendFetch("/admin/products/p1", {
      method: "PATCH",
      body: { name: "Funda iPhone 15" },
    });

    const [, requestInit] = fetchSpy.mock.calls[0];
    const init = requestInit as RequestInit;
    expect(init.body).toBe(JSON.stringify({ name: "Funda iPhone 15" }));
    expect(init.headers).toMatchObject({
      Authorization: "Bearer real-jwt-token",
      "Content-Type": "application/json",
    });
  });

  it("returns backend_unavailable when the upstream fetch throws", async () => {
    GET_CLAIMS.mockResolvedValue({
      data: { claims: { sub: "admin-1" } },
      error: null,
    });
    GET_SESSION.mockResolvedValue({
      data: { session: { access_token: "real-jwt-token" } },
    });
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new TypeError("fetch failed"),
    );

    const adminBackendFetch = await importBackendFetch();
    const result = await adminBackendFetch("/admin/products");

    expect(result).toEqual({ outcome: "backend_unavailable" });
  });
});
