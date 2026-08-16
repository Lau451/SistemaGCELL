import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `GET /api/admin/stock` — proxy Route Handler for the catalog-wide stock
 * triage page. Mirrors the movements proxy's exact auth/error mocking
 * convention, plus the allowlisted query-param passthrough required by
 * design.md Decision 5: only `below` and `search` are forwarded, rebuilt
 * into a fresh `URLSearchParams` — never `request.url`'s raw search string.
 */

const ADMIN_BACKEND_FETCH = vi.fn();

vi.mock("@/lib/admin/backend-fetch", () => ({
  adminBackendFetch: (...args: unknown[]) => ADMIN_BACKEND_FETCH(...args),
}));

async function importRoute() {
  const routeModule = await import("../route");
  return routeModule.GET;
}

describe("GET /api/admin/stock", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("returns 401 unauthenticated when the relay reports no session, without calling fetch", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({ outcome: "unauthenticated" });

    const GET = await importRoute();
    const response = await GET(new Request("http://x/api/admin/stock"));

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ error: "unauthenticated" });
    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledTimes(1);
  });

  it("returns 502 backend_unavailable when the relay cannot reach the backend", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({ outcome: "backend_unavailable" });

    const GET = await importRoute();
    const response = await GET(new Request("http://x/api/admin/stock"));

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ error: "backend_unavailable" });
  });

  it("relays to GET /admin/stock with no query string when none is given", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: [],
    });

    const GET = await importRoute();
    const response = await GET(new Request("http://x/api/admin/stock"));

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith("/admin/stock");
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual([]);
  });

  it("forwards below and search into a freshly rebuilt query string", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: [],
    });

    const GET = await importRoute();
    await GET(new Request("http://x/api/admin/stock?below=5&search=foo"));

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/stock?below=5&search=foo",
    );
  });

  it("drops an injected arbitrary query param, never forwarding it to the backend", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: [],
    });

    const GET = await importRoute();
    await GET(
      new Request("http://x/api/admin/stock?below=1&limit=999"),
    );

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith("/admin/stock?below=1");
  });

  it("sets a private, no-store Cache-Control header on the response", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: [],
    });

    const GET = await importRoute();
    const response = await GET(new Request("http://x/api/admin/stock"));

    expect(response.headers.get("Cache-Control")).toBe(
      "private, no-store",
    );
  });
});
