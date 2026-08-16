import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `/admin/stock` — catalog-wide, per-variant stock triage list. A Server
 * Component that fetches `/api/admin/stock` (design.md's Data Flow: "fetch
 * same-origin"), forwarding the incoming request's cookie by hand exactly
 * like `admin/products/page.tsx` (see that test file's header comment for
 * why). `next/headers`' `headers()` is mocked, and `fetch` is mocked so
 * this test needs no live backend.
 *
 * Covers design.md Decision 6 (two distinct empty-state strings), Decision 7
 * (searchParams Promise + array-collapse), and D13 (row links to the
 * product detail page).
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

function searchParamsOf(params: Record<string, string | string[] | undefined>) {
  return Promise.resolve(params);
}

describe("AdminStockPage", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("renders one row per variant with product name, model, color and quantity", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            product_id: "p1",
            product_slug: "funda-iphone-15",
            product_name: "Funda iPhone 15",
            product_model: "iPhone 15",
            variant_id: "v1",
            color: "negro",
            quantity_on_hand: 12,
          },
          {
            product_id: "p2",
            product_slug: "cargador-usb-c",
            product_name: "Cargador USB-C",
            product_model: "USB-C 20W",
            variant_id: "v2",
            color: "blanco",
            quantity_on_hand: 3,
          },
        ]),
    } as Response);

    const AdminStockPage = await importPage();
    const jsx = await AdminStockPage({ searchParams: searchParamsOf({}) });
    render(jsx);

    expect(screen.getByText("Funda iPhone 15")).toBeInTheDocument();
    expect(screen.getByText("iPhone 15")).toBeInTheDocument();
    expect(screen.getByText("negro")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();

    expect(screen.getByText("Cargador USB-C")).toBeInTheDocument();
    expect(screen.getByText("USB-C 20W")).toBeInTheDocument();
    expect(screen.getByText("blanco")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("links each row to /admin/products/{product_id}", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            product_id: "p1",
            product_slug: "funda-iphone-15",
            product_name: "Funda iPhone 15",
            product_model: "iPhone 15",
            variant_id: "v1",
            color: "negro",
            quantity_on_hand: 12,
          },
        ]),
    } as Response);

    const AdminStockPage = await importPage();
    const jsx = await AdminStockPage({ searchParams: searchParamsOf({}) });
    render(jsx);

    expect(
      screen.getByRole("link", { name: /funda iphone 15/i }),
    ).toHaveAttribute("href", "/admin/products/p1");
  });

  it("renders a zero-quantity row with text-destructive and Out of stock", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            product_id: "p1",
            product_slug: "funda-iphone-15",
            product_name: "Funda iPhone 15",
            product_model: "iPhone 15",
            variant_id: "v1",
            color: "negro",
            quantity_on_hand: 0,
          },
        ]),
    } as Response);

    const AdminStockPage = await importPage();
    const jsx = await AdminStockPage({ searchParams: searchParamsOf({}) });
    render(jsx);

    const label = screen.getByText("Out of stock");
    expect(label).toBeInTheDocument();
    expect(label.closest("td")).toHaveClass("text-destructive");
  });

  it('renders "No variants in the catalog yet." when there is no active filter and no rows', async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    } as Response);

    const AdminStockPage = await importPage();
    const jsx = await AdminStockPage({ searchParams: searchParamsOf({}) });
    render(jsx);

    expect(
      screen.getByText("No variants in the catalog yet."),
    ).toBeInTheDocument();
  });

  it('renders "No variants match your search or filter." when a filter is active and no rows', async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    } as Response);

    const AdminStockPage = await importPage();
    const jsx = await AdminStockPage({
      searchParams: searchParamsOf({ search: "nonexistent" }),
    });
    render(jsx);

    expect(
      screen.getByText("No variants match your search or filter."),
    ).toBeInTheDocument();
  });

  it("collapses an array-valued ?search=a&search=b to the first value and forwards it", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    } as Response);

    const AdminStockPage = await importPage();
    const jsx = await AdminStockPage({
      searchParams: searchParamsOf({ search: ["a", "b"] }),
    });
    render(jsx);

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [requestUrl] = fetchSpy.mock.calls[0];
    expect(String(requestUrl)).toBe(
      "http://localhost:3000/api/admin/stock?search=a",
    );
  });

  it("renders Unable to load stock. when the proxy fetch fails", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 502,
      json: () => Promise.resolve({ error: "backend_unavailable" }),
    } as Response);

    const AdminStockPage = await importPage();
    const jsx = await AdminStockPage({ searchParams: searchParamsOf({}) });
    render(jsx);

    expect(screen.getByText("Unable to load stock.")).toBeInTheDocument();
  });
});
