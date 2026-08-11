import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `GET /api/admin/products` — server-to-server proxy Route Handler per
 * design.md's "`GET /api/admin/products`" contract. `createSessionClient`
 * is mocked (per design.md's Testing Strategy: "Stubbed
 * `createSessionClient` + spied `fetch`") so this proves the auth gate
 * and proxying logic in isolation, without a live Supabase or FastAPI.
 *
 * FastAPI is the real trust boundary (design.md's "Technical Approach");
 * this route's own auth check is a routing optimization only — but it
 * MUST still short-circuit and never call `fetch` when there are no
 * claims, per the spec's "never reaches the repository" requirement
 * mirrored at this layer.
 *
 * @see design.md "`GET /api/admin/products`"
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

async function importRoute() {
  const routeModule = await import("../route");
  return routeModule.GET;
}

describe("GET /api/admin/products", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  it("returns 401 unauthenticated and never calls fetch when there are no claims", async () => {
    GET_CLAIMS.mockResolvedValue({
      data: null,
      error: { message: "invalid_token" },
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const GET = await importRoute();
    const response = await GET();

    expect(response.status).toBe(401);
    const body = await response.json();
    expect(body).toEqual({ error: "unauthenticated" });
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("returns 401 unauthenticated and never calls fetch when claims are empty", async () => {
    GET_CLAIMS.mockResolvedValue({ data: { claims: null }, error: null });
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const GET = await importRoute();
    const response = await GET();

    expect(response.status).toBe(401);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("proxies to the backend with a Bearer token when claims are present", async () => {
    GET_CLAIMS.mockResolvedValue({
      data: { claims: { sub: "admin-1" } },
      error: null,
    });
    GET_SESSION.mockResolvedValue({
      data: { session: { access_token: "real-jwt-token" } },
    });
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      status: 200,
      json: () => Promise.resolve([{ id: "p1", name: "Funda iPhone 15" }]),
    } as Response);

    const GET = await importRoute();
    const response = await GET();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [requestUrl, requestInit] = fetchSpy.mock.calls[0];
    expect(String(requestUrl)).toBe("http://127.0.0.1:8000/admin/products");
    expect((requestInit as RequestInit).headers).toEqual({
      Authorization: "Bearer real-jwt-token",
    });

    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body).toEqual([{ id: "p1", name: "Funda iPhone 15" }]);
  });

  it("returns 502 backend_unavailable when the upstream fetch throws", async () => {
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

    const GET = await importRoute();
    const response = await GET();

    expect(response.status).toBe(502);
    const body = await response.json();
    expect(body).toEqual({ error: "backend_unavailable" });
  });
});
