import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `/admin/products/[id]` — edit page. A Server Component fetching
 * `/api/admin/products/{id}` (same same-origin, cookie-forwarding
 * pattern as `products/page.tsx` — server-to-server RSC fetches do NOT
 * automatically carry the visiting browser's cookies). Renders
 * `product-form.tsx` wired to `updateProductAction`, bound to this
 * product's id; no slug field exposed anywhere (spec: "the edit form
 * MUST NOT expose a slug field to change").
 *
 * @see design.md "Data Flow", tasks.md 4.13
 */

const NOT_FOUND = vi.fn();

vi.mock("next/headers", () => ({
  headers: vi.fn(
    async () =>
      new Headers({ host: "localhost:3000", cookie: "sb-access-token=abc" }),
  ),
}));

const ROUTER_REFRESH = vi.fn();

vi.mock("next/navigation", () => ({
  notFound: (...args: unknown[]) => {
    NOT_FOUND(...args);
    throw new Error("NEXT_NOT_FOUND");
  },
  // `ImageManager` (Phase 7) calls `useRouter().refresh()` after a
  // mutation — this page's render tree now includes it, so the mock must
  // cover both exports the module tree needs. `StockHistory`'s date
  // filter (Phase 5-8) additionally needs `usePathname`/`useSearchParams`.
  useRouter: () => ({ refresh: ROUTER_REFRESH, push: vi.fn() }),
  usePathname: () => "/admin/products/p1",
  useSearchParams: () => new URLSearchParams(),
}));

// `ImageManager` resolves thumbnail `src` via the same public-URL builder
// the catalog pages use — mocked here the same way `api/catalog/route.test.ts`
// mocks it, so this test doesn't depend on a real `NEXT_PUBLIC_SUPABASE_URL`.
vi.mock("@/lib/supabase/env", () => ({
  getCatalogSupabaseEnv: () => ({
    url: "http://127.0.0.1:54321",
    anonKey: "anon-key",
  }),
}));

async function importPage() {
  const mod = await import("./page");
  return mod.default;
}

function paramsFor(
  id: string,
  searchParams: Record<string, string | string[] | undefined> = {},
) {
  return {
    params: Promise.resolve({ id }),
    searchParams: Promise.resolve(searchParams),
  };
}

describe("EditProductPage", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("fetches the product via /api/admin/products/{id}, forwarding the request cookie, and prefills the form", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = String(input);
        if (url.endsWith("/images")) {
          return {
            ok: true,
            json: () => Promise.resolve([]),
          } as Response;
        }
        if (url.endsWith("/stock")) {
          return {
            ok: true,
            json: () =>
              Promise.resolve([
                { variant_id: "v1", color: "negro", quantity_on_hand: 5 },
              ]),
          } as Response;
        }
        if (url.includes("/variants/") && url.endsWith("/stock/movements")) {
          return {
            ok: true,
            json: () =>
              Promise.resolve({
                items: [
                  {
                    id: 3,
                    variant_id: "v1",
                    movement_type: "restock",
                    quantity_delta: 8,
                    reason: null,
                    created_at: "2026-08-14T10:00:00Z",
                  },
                ],
                next_before_id: null,
              }),
          } as Response;
        }
        return {
          ok: true,
          json: () =>
            Promise.resolve({
              id: "p1",
              slug: "funda-iphone-15",
              name: "Funda iPhone 15",
              model: "iPhone 15",
              variants: [
                {
                  id: "v1",
                  color: "negro",
                  price: "5000.00",
                  cost: "2000.00",
                },
              ],
            }),
        } as Response;
      });

    const EditProductPage = await importPage();
    const jsx = await EditProductPage(paramsFor("p1"));
    render(jsx);

    expect(screen.getByLabelText(/^name$/i)).toHaveValue("Funda iPhone 15");
    expect(screen.getByLabelText(/^model$/i)).toHaveValue("iPhone 15");
    expect(screen.getByLabelText(/color/i)).toHaveValue("negro");
    expect(screen.queryByLabelText(/slug/i)).not.toBeInTheDocument();
    // `StockManager` (Phase B / PR2) renders below the images, sourced
    // from the new `fetchAdminProductStock` proxy call.
    expect(
      screen.getByText("negro", { selector: "span.font-medium" }),
    ).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    // `StockHistory` (Phase B / PR2) renders below `StockManager`, sourced
    // from the new `fetchAdminProductStockHistory` proxy call, prefetched
    // server-side for `variants[0]` only.
    expect(screen.getByText("Movement history")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("listitem")).toHaveTextContent("restock");

    // Product fetch, then images fetch, then stock fetch, then stock
    // history fetch — same self-referential, cookie-forwarded pattern for
    // all four.
    expect(fetchSpy).toHaveBeenCalledTimes(4);
    const [productUrl, productInit] = fetchSpy.mock.calls[0];
    expect(String(productUrl)).toBe(
      "http://localhost:3000/api/admin/products/p1",
    );
    expect((productInit as RequestInit).headers).toMatchObject({
      cookie: "sb-access-token=abc",
    });
    const [imagesUrl, imagesInit] = fetchSpy.mock.calls[1];
    expect(String(imagesUrl)).toBe(
      "http://localhost:3000/api/admin/products/p1/images",
    );
    expect((imagesInit as RequestInit).headers).toMatchObject({
      cookie: "sb-access-token=abc",
    });
    const [stockUrl, stockInit] = fetchSpy.mock.calls[2];
    expect(String(stockUrl)).toBe(
      "http://localhost:3000/api/admin/products/p1/stock",
    );
    expect((stockInit as RequestInit).headers).toMatchObject({
      cookie: "sb-access-token=abc",
    });
    const [historyUrl, historyInit] = fetchSpy.mock.calls[3];
    expect(String(historyUrl)).toBe(
      "http://localhost:3000/api/admin/products/p1/variants/v1/stock/movements",
    );
    expect((historyInit as RequestInit).headers).toMatchObject({
      cookie: "sb-access-token=abc",
    });
  });

  it("calls notFound() when the proxy route reports the product does not exist", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: "not_found" }),
    } as Response);

    const EditProductPage = await importPage();

    await expect(EditProductPage(paramsFor("missing"))).rejects.toThrow();
    expect(NOT_FOUND).toHaveBeenCalledTimes(1);
  });

  it("forwards since/until from searchParams via URLSearchParams to the movement-history fetch", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = String(input);
        if (url.endsWith("/images")) {
          return { ok: true, json: () => Promise.resolve([]) } as Response;
        }
        if (url.endsWith("/stock")) {
          return {
            ok: true,
            json: () =>
              Promise.resolve([
                { variant_id: "v1", color: "negro", quantity_on_hand: 5 },
              ]),
          } as Response;
        }
        if (url.includes("/variants/") && url.includes("/stock/movements")) {
          return {
            ok: true,
            json: () => Promise.resolve({ items: [], next_before_id: null }),
          } as Response;
        }
        return {
          ok: true,
          json: () =>
            Promise.resolve({
              id: "p1",
              slug: "funda-iphone-15",
              name: "Funda iPhone 15",
              model: "iPhone 15",
              variants: [
                { id: "v1", color: "negro", price: "5000.00", cost: "2000.00" },
              ],
            }),
        } as Response;
      });

    const EditProductPage = await importPage();
    const jsx = await EditProductPage(
      paramsFor("p1", {
        since: "2026-08-01T00:00:00.000000-03:00",
        until: "2026-08-15T23:59:59.999999-03:00",
      }),
    );
    render(jsx);

    const [historyUrl] = fetchSpy.mock.calls[3];
    const historyUrlString = String(historyUrl);
    expect(historyUrlString).toContain(
      "/api/admin/products/p1/variants/v1/stock/movements?",
    );
    const query = new URLSearchParams(historyUrlString.split("?")[1]);
    expect(query.get("since")).toBe("2026-08-01T00:00:00.000000-03:00");
    expect(query.get("until")).toBe("2026-08-15T23:59:59.999999-03:00");
  });

  it("renders the inverted-range guard and issues no fetch to the movements endpoint when since is after until", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = String(input);
        if (url.endsWith("/images")) {
          return { ok: true, json: () => Promise.resolve([]) } as Response;
        }
        if (url.endsWith("/stock")) {
          return {
            ok: true,
            json: () =>
              Promise.resolve([
                { variant_id: "v1", color: "negro", quantity_on_hand: 5 },
              ]),
          } as Response;
        }
        return {
          ok: true,
          json: () =>
            Promise.resolve({
              id: "p1",
              slug: "funda-iphone-15",
              name: "Funda iPhone 15",
              model: "iPhone 15",
              variants: [
                { id: "v1", color: "negro", price: "5000.00", cost: "2000.00" },
              ],
            }),
        } as Response;
      });

    const EditProductPage = await importPage();
    const jsx = await EditProductPage(
      paramsFor("p1", {
        since: "2026-08-20T00:00:00.000000-03:00",
        until: "2026-08-10T23:59:59.999999-03:00",
      }),
    );
    render(jsx);

    expect(screen.getByText("Start date is after end date.")).toBeInTheDocument();
    expect(screen.queryByText("Movement history")).not.toBeInTheDocument();
    expect(
      fetchSpy.mock.calls.some(([input]) =>
        String(input).includes("/stock/movements"),
      ),
    ).toBe(false);
  });
});
