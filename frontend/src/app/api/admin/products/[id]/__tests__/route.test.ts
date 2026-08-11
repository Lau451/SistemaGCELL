import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `GET /api/admin/products/[id]` — single-product proxy Route Handler for
 * the edit page. Relays directly to the backend's `GET /admin/products/{id}`
 * (added post-PR3 to close a design.md gap — see git history for the
 * superseded list-and-filter version this replaced).
 *
 * `@/lib/admin/backend-fetch` is mocked directly (rather than its own
 * transitive `@/lib/supabase/server` + `@/lib/admin/env` dependencies)
 * since this route's own logic is the relay-and-forward, not the auth
 * gate itself — that gate is already proven in isolation by
 * `backend-fetch.test.ts`.
 */

const ADMIN_BACKEND_FETCH = vi.fn();

vi.mock("@/lib/admin/backend-fetch", () => ({
  adminBackendFetch: (...args: unknown[]) => ADMIN_BACKEND_FETCH(...args),
}));

async function importRoute() {
  const routeModule = await import("../route");
  return routeModule.GET;
}

function paramsFor(id: string) {
  return { params: Promise.resolve({ id }) };
}

describe("GET /api/admin/products/[id]", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("returns 401 unauthenticated when the relay reports no session", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({ outcome: "unauthenticated" });

    const GET = await importRoute();
    const response = await GET(new Request("http://x"), paramsFor("p1"));

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ error: "unauthenticated" });
  });

  it("returns 502 backend_unavailable when the relay cannot reach the backend", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({ outcome: "backend_unavailable" });

    const GET = await importRoute();
    const response = await GET(new Request("http://x"), paramsFor("p1"));

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ error: "backend_unavailable" });
  });

  it("relays directly to GET /admin/products/{id} and forwards the response", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: { id: "p2", slug: "funda-iphone-16", name: "Funda iPhone 16" },
    });

    const GET = await importRoute();
    const response = await GET(new Request("http://x"), paramsFor("p2"));

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith("/admin/products/p2");
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({
      id: "p2",
      slug: "funda-iphone-16",
      name: "Funda iPhone 16",
    });
  });

  it("forwards a 404 from the backend unchanged when the product is unknown or retired", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 404,
      body: { detail: "not_found" },
    });

    const GET = await importRoute();
    const response = await GET(
      new Request("http://x"),
      paramsFor("does-not-exist"),
    );

    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ detail: "not_found" });
  });
});
