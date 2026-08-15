import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `StockHistory` — client component rendered below `StockManager` on the
 * product detail page (`[id]/page.tsx`), the read-only view of a variant's
 * recorded stock movements (spec: admin-stock-management "Admin Views
 * Per-Variant Movement History"). Owns local `useState` for the
 * accumulated entries + cursor (design.md Decision 6 — a deliberate
 * deviation from `stock-manager.tsx`'s "no local copy" convention, since an
 * append-in-place "Load more" list cannot be expressed by a server prop
 * alone).
 */

async function importStockHistory() {
  const mod = await import("./stock-history");
  return mod.StockHistory;
}

const PAGE_ONE = {
  items: [
    {
      id: 3,
      variant_id: "v1",
      movement_type: "sale",
      quantity_delta: -3,
      reason: null,
      created_at: "2026-08-14T10:00:00Z",
    },
    {
      id: 2,
      variant_id: "v1",
      movement_type: "restock",
      quantity_delta: 10,
      reason: "supplier delivery",
      created_at: "2026-08-13T10:00:00Z",
    },
  ],
  next_before_id: 2,
};

const PAGE_TWO = {
  items: [
    {
      id: 1,
      variant_id: "v1",
      movement_type: "restock",
      quantity_delta: 5,
      reason: null,
      created_at: "2026-08-12T10:00:00Z",
    },
  ],
  next_before_id: null,
};

const EMPTY_PAGE = { items: [], next_before_id: null };

describe("StockHistory", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it("renders an empty state, not an error, when the variant has no movements", async () => {
    const StockHistory = await importStockHistory();

    render(
      <StockHistory
        productId="p1"
        variantId="v1"
        initialHistory={EMPTY_PAGE}
      />,
    );

    expect(screen.getByText(/no movements/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("renders movements newest-first, in the order the page provides", async () => {
    const StockHistory = await importStockHistory();

    render(
      <StockHistory
        productId="p1"
        variantId="v1"
        initialHistory={PAGE_ONE}
      />,
    );

    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveTextContent("sale");
    expect(rows[1]).toHaveTextContent("restock");
  });

  it("appends the next page below existing rows without resetting the list on Load more", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(PAGE_TWO),
    } as Response);
    const user = userEvent.setup();
    const StockHistory = await importStockHistory();

    render(
      <StockHistory
        productId="p1"
        variantId="v1"
        initialHistory={PAGE_ONE}
      />,
    );

    await user.click(screen.getByRole("button", { name: /load more/i }));

    await waitFor(() => {
      expect(screen.getAllByRole("listitem")).toHaveLength(3);
    });
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("sale");
    expect(rows[1]).toHaveTextContent("restock");
    expect(rows[2]).toHaveTextContent("restock");

    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/admin/products/p1/variants/v1/stock/movements?before_id=2",
      { cache: "no-store" },
    );
  });

  it("does not render Load more once next_before_id is null", async () => {
    const StockHistory = await importStockHistory();

    render(
      <StockHistory
        productId="p1"
        variantId="v1"
        initialHistory={PAGE_TWO}
      />,
    );

    expect(
      screen.queryByRole("button", { name: /load more/i }),
    ).not.toBeInTheDocument();
  });

  it("does not render a running-balance column or any type/date filter controls", async () => {
    const StockHistory = await importStockHistory();

    render(
      <StockHistory
        productId="p1"
        variantId="v1"
        initialHistory={PAGE_ONE}
      />,
    );

    expect(screen.queryByText(/balance/i)).not.toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: /type/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByLabelText(/date/i),
    ).not.toBeInTheDocument();
  });

  it("resets entries and cursor to page one when the initialHistory prop reference changes", async () => {
    const StockHistory = await importStockHistory();

    const { rerender } = render(
      <StockHistory
        productId="p1"
        variantId="v1"
        initialHistory={PAGE_ONE}
      />,
    );

    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(
      screen.getByRole("button", { name: /load more/i }),
    ).toBeInTheDocument();

    // A NEW object reference (e.g. after router.refresh() re-runs the
    // server fetch) for a different variant with only one movement and no
    // further pages — must reset, not merge with the prior page's rows.
    const freshSingleEntry = {
      items: [
        {
          id: 9,
          variant_id: "v2",
          movement_type: "return",
          quantity_delta: 1,
          reason: null,
          created_at: "2026-08-15T09:00:00Z",
        },
      ],
      next_before_id: null,
    };

    rerender(
      <StockHistory
        productId="p1"
        variantId="v2"
        initialHistory={freshSingleEntry}
      />,
    );

    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("return");
    expect(
      screen.queryByRole("button", { name: /load more/i }),
    ).not.toBeInTheDocument();
  });
});
