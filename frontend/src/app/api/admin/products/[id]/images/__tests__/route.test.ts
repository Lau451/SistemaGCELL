import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `GET /api/admin/products/[id]/images` — image-list proxy Route Handler
 * for the product detail page. Relays directly to the backend's
 * `GET /admin/products/{id}/images`, mirroring
 * `[id]/__tests__/route.test.ts`'s exact mocking convention.
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

describe("GET /api/admin/products/[id]/images", () => {
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

  it("relays directly to GET /admin/products/{id}/images and forwards the list", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: [
        {
          id: "img1",
          product_id: "p2",
          variant_id: null,
          storage_path: "funda-iphone-16/hero-abc123.webp",
          alt_text: null,
          sort_order: 0,
        },
      ],
    });

    const GET = await importRoute();
    const response = await GET(new Request("http://x"), paramsFor("p2"));

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/products/p2/images",
    );
    expect(response.status).toBe(200);
    expect(await response.json()).toEqual([
      {
        id: "img1",
        product_id: "p2",
        variant_id: null,
        storage_path: "funda-iphone-16/hero-abc123.webp",
        alt_text: null,
        sort_order: 0,
      },
    ]);
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
