import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `/admin/products` — the ONE read-only proof page this change ships
 * (`product_decisions.scope`, `state.yaml`). A Server Component that
 * fetches `/api/admin/products` (design.md's Data Flow: "fetch
 * same-origin"). Because this is a server-to-server request from an
 * RSC (not a browser fetch), the incoming request's `cookie` header
 * MUST be forwarded manually — a plain relative/absolute `fetch()` from
 * server code does NOT carry the visiting browser's session cookie on
 * its own, so `createSessionClient()` inside the proxy route would see
 * no session and always 401 without this. `next/headers`' `headers()`
 * is mocked to prove that forwarding, and `fetch` is mocked so this
 * test needs no live backend.
 */

vi.mock("next/headers", () => ({
  headers: vi.fn(
    async () =>
      new Headers({ host: "localhost:3000", cookie: "sb-access-token=abc" }),
  ),
}));

async function importPage() {
  const mod = await import("./page");
  return mod.default;
}

describe("AdminProductsPage", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("renders product/variant rows returned by /api/admin/products, forwarding the request cookie", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            id: "p1",
            slug: "funda-iphone-15",
            name: "Funda iPhone 15",
            model: "iPhone 15",
            variants: [
              { id: "v1", color: "negro", price: "5000", cost: "2000" },
            ],
          },
        ]),
    } as Response);

    const AdminProductsPage = await importPage();
    const jsx = await AdminProductsPage();
    render(jsx);

    expect(screen.getByText("Funda iPhone 15")).toBeInTheDocument();
    expect(screen.getByText("negro")).toBeInTheDocument();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [requestUrl, requestInit] = fetchSpy.mock.calls[0];
    expect(String(requestUrl)).toBe(
      "http://localhost:3000/api/admin/products",
    );
    expect((requestInit as RequestInit).headers).toMatchObject({
      cookie: "sb-access-token=abc",
    });
  });

  it("renders an error state when the proxy route fails, without throwing", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 502,
      json: () => Promise.resolve({ error: "backend_unavailable" }),
    } as Response);

    const AdminProductsPage = await importPage();
    const jsx = await AdminProductsPage();
    render(jsx);

    expect(screen.getByText(/unable to load products/i)).toBeInTheDocument();
  });
});
