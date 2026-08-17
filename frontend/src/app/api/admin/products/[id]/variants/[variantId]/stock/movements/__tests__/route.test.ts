import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `GET /api/admin/products/[id]/variants/[variantId]/stock/movements` —
 * proxy Route Handler for a variant's stock movement history. Mirrors
 * `[id]/stock/__tests__/route.test.ts`'s exact auth/error mocking
 * convention, plus the allowlisted query-param passthrough required by
 * design.md Decision 7 / D9: `limit`, `before_id`, `since` and `until`
 * are forwarded, rebuilt into a fresh `URLSearchParams` — never
 * `request.url`'s raw search string. `variant` is deliberately NOT
 * allowlisted (design.md File Changes: it is a page-level view key, and
 * the variant already lives in the path).
 */

const ADMIN_BACKEND_FETCH = vi.fn();

vi.mock("@/lib/admin/backend-fetch", () => ({
  adminBackendFetch: (...args: unknown[]) => ADMIN_BACKEND_FETCH(...args),
}));

async function importRoute() {
  const routeModule = await import("../route");
  return routeModule.GET;
}

function paramsFor(id: string, variantId: string) {
  return { params: Promise.resolve({ id, variantId }) };
}

describe("GET /api/admin/products/[id]/variants/[variantId]/stock/movements", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("returns 401 unauthenticated when the relay reports no session", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({ outcome: "unauthenticated" });

    const GET = await importRoute();
    const response = await GET(new Request("http://x"), paramsFor("p1", "v1"));

    expect(response.status).toBe(401);
    expect(await response.json()).toEqual({ error: "unauthenticated" });
  });

  it("returns 502 backend_unavailable when the relay cannot reach the backend", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({ outcome: "backend_unavailable" });

    const GET = await importRoute();
    const response = await GET(new Request("http://x"), paramsFor("p1", "v1"));

    expect(response.status).toBe(502);
    expect(await response.json()).toEqual({ error: "backend_unavailable" });
  });

  it("relays to GET /admin/products/{id}/variants/{variantId}/stock/movements with no query string when none is given", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: { items: [], next_before_id: null },
    });

    const GET = await importRoute();
    const response = await GET(
      new Request("http://x/api/admin/products/p1/variants/v1/stock/movements"),
      paramsFor("p1", "v1"),
    );

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/products/p1/variants/v1/stock/movements",
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ items: [], next_before_id: null });
  });

  it("forwards only limit and before_id, dropping an injected arbitrary query param", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: { items: [], next_before_id: null },
    });

    const GET = await importRoute();
    await GET(
      new Request(
        "http://x/api/admin/products/p1/variants/v1/stock/movements?limit=5&before_id=42&evil=1&another=drop-me",
      ),
      paramsFor("p1", "v1"),
    );

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/products/p1/variants/v1/stock/movements?limit=5&before_id=42",
    );
  });

  it("forwards limit, before_id, since and until — dropping a fifth injected param", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: { items: [], next_before_id: null },
    });

    const GET = await importRoute();
    await GET(
      new Request(
        "http://x/api/admin/products/p1/variants/v1/stock/movements?limit=5&before_id=42&since=2026-08-01T00%3A00%3A00.000000-03%3A00&until=2026-08-15T23%3A59%3A59.999999-03%3A00&evil=1",
      ),
      paramsFor("p1", "v1"),
    );

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/products/p1/variants/v1/stock/movements?limit=5&before_id=42&since=2026-08-01T00%3A00%3A00.000000-03%3A00&until=2026-08-15T23%3A59%3A59.999999-03%3A00",
    );
  });

  it("drops an injected variant param — it is a page-level view key, not forwarded to the backend", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: { items: [], next_before_id: null },
    });

    const GET = await importRoute();
    await GET(
      new Request(
        "http://x/api/admin/products/p1/variants/v1/stock/movements?since=2026-08-01T00%3A00%3A00.000000-03%3A00&variant=v2",
      ),
      paramsFor("p1", "v1"),
    );

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/products/p1/variants/v1/stock/movements?since=2026-08-01T00%3A00%3A00.000000-03%3A00",
    );
  });

  it("a raw +HH:MM offset survives the round trip through the fresh URLSearchParams rebuild", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: { items: [], next_before_id: null },
    });

    const GET = await importRoute();
    const incomingQuery = new URLSearchParams();
    incomingQuery.set("since", "2026-08-01T00:00:00.000000+02:00");
    await GET(
      new Request(
        `http://x/api/admin/products/p1/variants/v1/stock/movements?${incomingQuery.toString()}`,
      ),
      paramsFor("p1", "v1"),
    );

    const [forwardedPath] = ADMIN_BACKEND_FETCH.mock.calls[0];
    // The raw offset must never appear unencoded — a literal space in its
    // place is exactly the corruption a naive `request.url.search` forward
    // (rather than a fresh `URLSearchParams` rebuild) would produce.
    expect(forwardedPath).not.toContain(" ");
    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/products/p1/variants/v1/stock/movements?since=2026-08-01T00%3A00%3A00.000000%2B02%3A00",
    );
  });

  it("forwards a 404 from the backend unchanged when the variant is unknown or foreign", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 404,
      body: { detail: "not_found" },
    });

    const GET = await importRoute();
    const response = await GET(
      new Request("http://x/api/admin/products/p1/variants/does-not-exist/stock/movements"),
      paramsFor("p1", "does-not-exist"),
    );

    expect(response.status).toBe(404);
    expect(await response.json()).toEqual({ detail: "not_found" });
  });
});
