import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `/admin/products/[id]/stock` — stock management page. A Server
 * Component fetching `/api/admin/products/{id}` (same same-origin,
 * cookie-forwarding pattern as `products/page.tsx` — server-to-server RSC
 * fetches do NOT automatically carry the visiting browser's cookies).
 *
 * Split out of the combined `/admin/products/[id]` page: covers
 * `StockManager`, `StockHistory`, `VariantSwitcher`, the `?variant=`
 * membership check (DD4), the `since`/`until` date-filter handling (DD1/
 * DD2), and the zero-variants guard. Product-info-form/image-manager
 * coverage lives in `[id]/page.test.tsx`.
 *
 * @see design.md "Data Flow", "DD1", "DD2", "DD3", "DD4"
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
  // `StockManager` calls `useRouter().refresh()` after a mutation.
  // `StockHistory`'s date filter needs `usePathname`/`useSearchParams`.
  useRouter: () => ({ refresh: ROUTER_REFRESH, push: vi.fn() }),
  usePathname: () => "/admin/products/p1/stock",
  useSearchParams: () => new URLSearchParams(),
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

describe("ProductStockPage", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("fetches the product, stock, and default variant's history, forwarding the request cookie", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = String(input);
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

    const ProductStockPage = await importPage();
    const jsx = await ProductStockPage(paramsFor("p1"));
    render(jsx);

    expect(
      screen.getByRole("heading", { name: "Stock — Funda iPhone 15" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /editar producto/i }),
    ).toHaveAttribute("href", "/admin/products/p1");
    // `StockManager` renders the current stock list.
    expect(
      screen.getByText("negro", { selector: "span.font-medium" }),
    ).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    // `StockHistory` renders below `StockManager`, sourced from the
    // movement-history proxy, prefetched server-side for `variants[0]`.
    expect(screen.getByText("Historial de movimientos")).toBeInTheDocument();
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("listitem")).toHaveTextContent("restock");

    // Product fetch, then stock fetch, then stock history fetch — same
    // self-referential, cookie-forwarded pattern for all three.
    expect(fetchSpy).toHaveBeenCalledTimes(3);
    const [productUrl, productInit] = fetchSpy.mock.calls[0];
    expect(String(productUrl)).toBe(
      "http://localhost:3000/api/admin/products/p1",
    );
    expect((productInit as RequestInit).headers).toMatchObject({
      cookie: "sb-access-token=abc",
    });
    const [stockUrl, stockInit] = fetchSpy.mock.calls[1];
    expect(String(stockUrl)).toBe(
      "http://localhost:3000/api/admin/products/p1/stock",
    );
    expect((stockInit as RequestInit).headers).toMatchObject({
      cookie: "sb-access-token=abc",
    });
    const [historyUrl, historyInit] = fetchSpy.mock.calls[2];
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

    const ProductStockPage = await importPage();

    await expect(ProductStockPage(paramsFor("missing"))).rejects.toThrow();
    expect(NOT_FOUND).toHaveBeenCalledTimes(1);
  });

  it("forwards since/until from searchParams via URLSearchParams to the movement-history fetch", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(async (input) => {
        const url = String(input);
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

    const ProductStockPage = await importPage();
    const jsx = await ProductStockPage(
      paramsFor("p1", {
        since: "2026-08-01T00:00:00.000000-03:00",
        until: "2026-08-15T23:59:59.999999-03:00",
      }),
    );
    render(jsx);

    const [historyUrl] = fetchSpy.mock.calls[2];
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

    const ProductStockPage = await importPage();
    const jsx = await ProductStockPage(
      paramsFor("p1", {
        since: "2026-08-20T00:00:00.000000-03:00",
        until: "2026-08-10T23:59:59.999999-03:00",
      }),
    );
    render(jsx);

    expect(screen.getByText("La fecha de inicio es posterior a la fecha de fin.")).toBeInTheDocument();
    expect(screen.queryByText("Historial de movimientos")).not.toBeInTheDocument();
    expect(
      fetchSpy.mock.calls.some(([input]) =>
        String(input).includes("/stock/movements"),
      ),
    ).toBe(false);
  });

  /**
   * `?variant=` resolution, the `VariantSwitcher` render, and D16's
   * no-coupling guarantee for `StockManager`.
   */
  function mockTwoVariantFetch() {
    return vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/stock")) {
        return {
          ok: true,
          json: () =>
            Promise.resolve([
              { variant_id: "v1", color: "negro", quantity_on_hand: 5 },
              { variant_id: "v2", color: "azul", quantity_on_hand: 2 },
            ]),
        } as Response;
      }
      if (url.includes("/variants/v2/") && url.includes("/stock/movements")) {
        return {
          ok: true,
          json: () =>
            Promise.resolve({
              items: [
                {
                  id: 9,
                  variant_id: "v2",
                  movement_type: "sale",
                  quantity_delta: -1,
                  reason: null,
                  created_at: "2026-08-15T10:00:00Z",
                },
              ],
              next_before_id: null,
            }),
        } as Response;
      }
      if (url.includes("/variants/v1/") && url.includes("/stock/movements")) {
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
              { id: "v2", color: "azul", price: "5500.00", cost: "2200.00" },
            ],
          }),
      } as Response;
    });
  }

  it("absent ?variant defaults to the first variant, and the switcher marks it active", async () => {
    const fetchSpy = mockTwoVariantFetch();

    const ProductStockPage = await importPage();
    const jsx = await ProductStockPage(paramsFor("p1"));
    render(jsx);

    expect(
      fetchSpy.mock.calls.some(([input]) =>
        String(input).includes("/variants/v1/stock/movements"),
      ),
    ).toBe(true);
    expect(screen.getByRole("link", { name: "negro" })).toHaveAttribute(
      "aria-current",
      "page",
    );
  });

  it("a valid ?variant fetches that variant's history and the switcher marks it active", async () => {
    const fetchSpy = mockTwoVariantFetch();

    const ProductStockPage = await importPage();
    const jsx = await ProductStockPage(paramsFor("p1", { variant: "v2" }));
    render(jsx);

    expect(
      fetchSpy.mock.calls.some(([input]) =>
        String(input).includes("/variants/v2/stock/movements"),
      ),
    ).toBe(true);
    expect(
      fetchSpy.mock.calls.some(([input]) =>
        String(input).includes("/variants/v1/stock/movements"),
      ),
    ).toBe(false);
    expect(screen.getByRole("link", { name: "azul" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    expect(screen.getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getByRole("listitem")).toHaveTextContent("sale");
  });

  it("a nonexistent ?variant calls notFound() and issues no movements request", async () => {
    const fetchSpy = mockTwoVariantFetch();

    const ProductStockPage = await importPage();

    await expect(
      ProductStockPage(paramsFor("p1", { variant: "does-not-exist" })),
    ).rejects.toThrow();
    expect(NOT_FOUND).toHaveBeenCalledTimes(1);
    expect(
      fetchSpy.mock.calls.some(([input]) =>
        String(input).includes("/stock/movements"),
      ),
    ).toBe(false);
  });

  it("a malformed ?variant value calls notFound()", async () => {
    mockTwoVariantFetch();

    const ProductStockPage = await importPage();

    await expect(
      ProductStockPage(paramsFor("p1", { variant: "not-a-uuid" })),
    ).rejects.toThrow();
    expect(NOT_FOUND).toHaveBeenCalledTimes(1);
  });

  it("switcher links preserve the active since/until date filter", async () => {
    mockTwoVariantFetch();

    const ProductStockPage = await importPage();
    const jsx = await ProductStockPage(
      paramsFor("p1", {
        since: "2026-08-01T00:00:00.000000-03:00",
        until: "2026-08-15T23:59:59.999999-03:00",
      }),
    );
    render(jsx);

    const azulHref = screen
      .getByRole("link", { name: "azul" })
      .getAttribute("href")!;
    const query = new URLSearchParams(azulHref.split("?")[1]);
    expect(query.get("variant")).toBe("v2");
    expect(query.get("since")).toBe("2026-08-01T00:00:00.000000-03:00");
    expect(query.get("until")).toBe("2026-08-15T23:59:59.999999-03:00");
  });

  it("StockManager's rendering is unaffected by ?variant (D16 — no coupling)", async () => {
    mockTwoVariantFetch();

    const ProductStockPage = await importPage();
    const jsx = await ProductStockPage(paramsFor("p1", { variant: "v2" }));
    render(jsx);

    // `StockManager`'s write-target `<select>` still defaults to the
    // FIRST stock entry (`stock[0]?.variant_id`), regardless of which
    // variant `?variant=` selects for the read-only history view — D16.
    expect(screen.getByLabelText(/^variante$/i)).toHaveValue("v1");
    // Both variants still appear in the write-target select's options,
    // unfiltered by the active `?variant=`.
    const variantSelect = screen.getByLabelText(
      /^variante$/i,
    ) as HTMLSelectElement;
    const optionLabels = Array.from(variantSelect.options).map(
      (option) => option.textContent,
    );
    expect(optionLabels).toEqual(["negro", "azul"]);
  });

  it("a product with zero variants stays reachable and does not 404 (locked spec: A Product May Have Zero Active Variants Without Being Retired)", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/stock")) {
        return { ok: true, json: () => Promise.resolve([]) } as Response;
      }
      return {
        ok: true,
        json: () =>
          Promise.resolve({
            id: "p1",
            slug: "funda-iphone-15",
            name: "Funda iPhone 15",
            model: "iPhone 15",
            variants: [],
          }),
      } as Response;
    });

    const ProductStockPage = await importPage();
    const jsx = await ProductStockPage(paramsFor("p1"));
    render(jsx);

    expect(NOT_FOUND).not.toHaveBeenCalled();
    expect(
      screen.getByRole("heading", { name: "Stock — Funda iPhone 15" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Historial de movimientos")).not.toBeInTheDocument();
  });
});
