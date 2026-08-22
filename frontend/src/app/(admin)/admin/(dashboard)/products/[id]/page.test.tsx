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
 * Stock management (record-movement form, history, variant switcher) is
 * covered by `[id]/stock/page.test.tsx` — this page is product-info-only.
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
  // cover both exports the module tree needs.
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

function paramsFor(id: string) {
  return {
    params: Promise.resolve({ id }),
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

    expect(screen.getByLabelText(/^nombre$/i)).toHaveValue("Funda iPhone 15");
    expect(screen.getByLabelText(/^modelo$/i)).toHaveValue("iPhone 15");
    expect(screen.getByLabelText(/color/i)).toHaveValue("negro");
    expect(screen.queryByLabelText(/slug/i)).not.toBeInTheDocument();
    // No stock section on this page anymore — split out to
    // `[id]/stock/page.tsx`.
    expect(
      screen.queryByText("Historial de movimientos"),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Stock" })).not.toBeInTheDocument();
    // A link to the stock page is rendered near the heading.
    expect(screen.getByRole("link", { name: /ver stock/i })).toHaveAttribute(
      "href",
      "/admin/products/p1/stock",
    );

    // Product fetch, then images fetch — same self-referential,
    // cookie-forwarded pattern for both.
    expect(fetchSpy).toHaveBeenCalledTimes(2);
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

  it("a product with zero variants stays editable and does not 404 (locked spec: A Product May Have Zero Active Variants Without Being Retired)", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.endsWith("/images")) {
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

    const EditProductPage = await importPage();
    const jsx = await EditProductPage(paramsFor("p1"));
    render(jsx);

    expect(NOT_FOUND).not.toHaveBeenCalled();
    expect(screen.getByLabelText(/^nombre$/i)).toHaveValue("Funda iPhone 15");
  });
});
