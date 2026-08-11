import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `/admin/products` — the admin product list. A Server Component that
 * fetches `/api/admin/products` (design.md's Data Flow: "fetch
 * same-origin"). Because this is a server-to-server request from an
 * RSC (not a browser fetch), the incoming request's `cookie` header
 * MUST be forwarded manually — a plain relative/absolute `fetch()` from
 * server code does NOT carry the visiting browser's session cookie on
 * its own, so `createSessionClient()` inside the proxy route would see
 * no session and always 401 without this. `next/headers`' `headers()`
 * is mocked to prove that forwarding, and `fetch` is mocked so this
 * test needs no live backend.
 *
 * PR4 adds a "New product" link, a per-product Edit link, and a
 * per-product Retire form/button (`retireProductAction`, mocked here —
 * already covered in isolation by `actions.test.ts`). The listing is
 * grouped one row per PRODUCT (not one row per variant, as the PR2/PR3-
 * era page did) — a product with zero active variants must still appear,
 * editable (spec: "A Product May Have Zero Active Variants Without Being
 * Retired"), which a per-variant-row `flatMap` cannot render at all for
 * an empty `variants` array.
 */

const RETIRE_PRODUCT_ACTION = vi.fn();

vi.mock("next/headers", () => ({
  headers: vi.fn(
    async () =>
      new Headers({ host: "localhost:3000", cookie: "sb-access-token=abc" }),
  ),
}));

vi.mock("./actions", () => ({
  retireProductAction: (...args: unknown[]) => RETIRE_PRODUCT_ACTION(...args),
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

  it("renders one row per product, forwarding the request cookie", async () => {
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
    expect(screen.getByText(/negro/)).toBeInTheDocument();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [requestUrl, requestInit] = fetchSpy.mock.calls[0];
    expect(String(requestUrl)).toBe(
      "http://localhost:3000/api/admin/products",
    );
    expect((requestInit as RequestInit).headers).toMatchObject({
      cookie: "sb-access-token=abc",
    });
  });

  it("still lists a product with zero active variants, editable", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            id: "p1",
            slug: "funda-iphone-15",
            name: "Funda iPhone 15",
            model: "iPhone 15",
            variants: [],
          },
        ]),
    } as Response);

    const AdminProductsPage = await importPage();
    const jsx = await AdminProductsPage();
    render(jsx);

    expect(screen.getByText("Funda iPhone 15")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /edit/i }),
    ).toHaveAttribute("href", "/admin/products/p1");
  });

  it("renders a New product link to /admin/products/new", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    } as Response);

    const AdminProductsPage = await importPage();
    const jsx = await AdminProductsPage();
    render(jsx);

    expect(
      screen.getByRole("link", { name: /new product/i }),
    ).toHaveAttribute("href", "/admin/products/new");
  });

  it("renders a per-product Edit link to /admin/products/{id}", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            id: "p1",
            slug: "funda-iphone-15",
            name: "Funda iPhone 15",
            model: "iPhone 15",
            variants: [],
          },
        ]),
    } as Response);

    const AdminProductsPage = await importPage();
    const jsx = await AdminProductsPage();
    render(jsx);

    expect(
      screen.getByRole("link", { name: /edit/i }),
    ).toHaveAttribute("href", "/admin/products/p1");
  });

  it("submits retireProductAction with the product id from the Retire button", async () => {
    RETIRE_PRODUCT_ACTION.mockResolvedValue(undefined);
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            id: "p1",
            slug: "funda-iphone-15",
            name: "Funda iPhone 15",
            model: "iPhone 15",
            variants: [],
          },
        ]),
    } as Response);
    const user = userEvent.setup();

    const AdminProductsPage = await importPage();
    const jsx = await AdminProductsPage();
    render(jsx);

    await user.click(screen.getByRole("button", { name: /retire/i }));

    expect(RETIRE_PRODUCT_ACTION).toHaveBeenCalledTimes(1);
    const [formData] = RETIRE_PRODUCT_ACTION.mock.calls[0] as [FormData];
    expect(formData.get("product-id")).toBe("p1");
  });

  it("never renders a restore control or a show-retired filter/toggle", async () => {
    // Runtime regression guard for the spec's "No Restore Capability In
    // This Change" and "No Show-Retired Filter" requirements — these were
    // previously true only by omission (nothing built), which sdd-verify
    // flagged as PARTIAL since no test would catch either control being
    // added by accident later.
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            id: "p1",
            slug: "funda-iphone-15",
            name: "Funda iPhone 15",
            model: "iPhone 15",
            variants: [],
          },
        ]),
    } as Response);

    const AdminProductsPage = await importPage();
    const jsx = await AdminProductsPage();
    render(jsx);

    expect(screen.queryByText(/restore/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/retired/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/show.*deleted/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("checkbox", { name: /filter/i }),
    ).not.toBeInTheDocument();
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
