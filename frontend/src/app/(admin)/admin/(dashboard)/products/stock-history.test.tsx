import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { presetRange } from "./stock-history-dates";

/**
 * `StockHistory` — client component rendered below `StockManager` on the
 * product detail page (`[id]/page.tsx`), the read-only view of a variant's
 * recorded stock movements (spec: admin-stock-management "Admin Views
 * Per-Variant Movement History"). Owns local `useState` for the
 * accumulated entries + cursor (design.md Decision 6 — a deliberate
 * deviation from `stock-manager.tsx`'s "no local copy" convention, since an
 * append-in-place "Load more" list cannot be expressed by a server prop
 * alone).
 *
 * Date-range filter (design.md DD2/D13): the filter itself is URL-driven
 * — a preset click or a date-input change pushes `?since=&until=` via
 * `useRouter`, a real navigation, which is EXACTLY what produces the new
 * `initialHistory` prop reference the pre-existing Decision 6 reset
 * already handles. No new reset logic is written for the filter.
 */

const ROUTER_PUSH = vi.fn();
const ROUTER_REPLACE = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: ROUTER_PUSH, replace: ROUTER_REPLACE }),
  usePathname: () => "/admin/products/p1",
  useSearchParams: () => mockSearchParams,
}));

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
    vi.useRealTimers();
    mockSearchParams = new URLSearchParams();
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

    expect(screen.getByText(/todavía no hay movimientos/i)).toBeInTheDocument();
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

    await user.click(screen.getByRole("button", { name: /cargar más/i }));

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
      screen.queryByRole("button", { name: /cargar más/i }),
    ).not.toBeInTheDocument();
  });

  it("does not render a running-balance column or any movement-type filter control", async () => {
    // Date-range filtering is now in scope (D3 reverses only the
    // date-range half of the old MUST NOT clause) — the movement-type
    // half and the no-balance clause stay locked and are still asserted
    // here.
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
  });

  it("renders the date-range inputs and the three preset + Clear controls", async () => {
    const StockHistory = await importStockHistory();

    render(
      <StockHistory
        productId="p1"
        variantId="v1"
        initialHistory={PAGE_ONE}
      />,
    );

    expect(screen.getByLabelText(/desde/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/hasta/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^hoy$/i })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /últimos 7 días/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /últimos 30 días/i }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /limpiar/i })).toBeInTheDocument();
  });

  it('renders "No hay movimientos en el rango de fechas seleccionado." when a filter is active and yields zero rows (D13)', async () => {
    const StockHistory = await importStockHistory();

    render(
      <StockHistory
        productId="p1"
        variantId="v1"
        initialHistory={EMPTY_PAGE}
        since="2026-08-01T00:00:00.000000-03:00"
        until="2026-08-15T23:59:59.999999-03:00"
      />,
    );

    expect(
      screen.getByText("No hay movimientos en el rango de fechas seleccionado."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Todavía no hay movimientos registrados.")).not.toBeInTheDocument();
  });

  it('renders "Todavía no hay movimientos registrados." (unchanged copy) when no filter is active (D13)', async () => {
    const StockHistory = await importStockHistory();

    render(
      <StockHistory
        productId="p1"
        variantId="v1"
        initialHistory={EMPTY_PAGE}
      />,
    );

    expect(screen.getByText("Todavía no hay movimientos registrados.")).toBeInTheDocument();
  });

  it("clicking the last-7-days preset pushes the URL with the exact presetRange('last7') query", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(2026, 7, 15));
    vi.spyOn(Date.prototype, "getTimezoneOffset").mockReturnValue(180);
    const expected = presetRange("last7");
    const StockHistory = await importStockHistory();

    render(
      <StockHistory
        productId="p1"
        variantId="v1"
        initialHistory={PAGE_ONE}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /últimos 7 días/i }));

    const expectedParams = new URLSearchParams();
    expectedParams.set("since", expected.since);
    expectedParams.set("until", expected.until);
    expect(ROUTER_PUSH).toHaveBeenCalledWith(
      `/admin/products/p1?${expectedParams.toString()}`,
    );
  });

  it("changing the Since date input pushes the URL with the converted since param, preserving until", async () => {
    vi.spyOn(Date.prototype, "getTimezoneOffset").mockReturnValue(180);
    const StockHistory = await importStockHistory();

    render(
      <StockHistory
        productId="p1"
        variantId="v1"
        initialHistory={PAGE_ONE}
        until="2026-08-15T23:59:59.999999-03:00"
      />,
    );

    fireEvent.change(screen.getByLabelText(/desde/i), {
      target: { value: "2026-08-01" },
    });

    const call = ROUTER_PUSH.mock.calls.at(-1)?.[0] as string;
    const pushedParams = new URLSearchParams(call.split("?")[1]);
    expect(pushedParams.get("since")).toBe("2026-08-01T00:00:00.000000-03:00");
    expect(pushedParams.get("until")).toBe("2026-08-15T23:59:59.999999-03:00");
  });

  it("clicking Clear pushes the URL with since/until removed but any other param preserved", async () => {
    mockSearchParams = new URLSearchParams(
      "since=2026-08-01T00%3A00%3A00.000000-03%3A00&until=2026-08-15T23%3A59%3A59.999999-03%3A00&foo=bar",
    );
    const user = userEvent.setup();
    const StockHistory = await importStockHistory();

    render(
      <StockHistory
        productId="p1"
        variantId="v1"
        initialHistory={PAGE_ONE}
        since="2026-08-01T00:00:00.000000-03:00"
        until="2026-08-15T23:59:59.999999-03:00"
      />,
    );

    await user.click(screen.getByRole("button", { name: /limpiar/i }));

    const call = ROUTER_PUSH.mock.calls.at(-1)?.[0] as string;
    const pushedParams = new URLSearchParams(call.split("?")[1] ?? "");
    expect(pushedParams.has("since")).toBe(false);
    expect(pushedParams.has("until")).toBe(false);
    expect(pushedParams.get("foo")).toBe("bar");
  });

  it("handleLoadMore re-sends the current since/until on the next page fetch", async () => {
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
        since="2026-08-01T00:00:00.000000-03:00"
        until="2026-08-15T23:59:59.999999-03:00"
      />,
    );

    await user.click(screen.getByRole("button", { name: /cargar más/i }));

    await waitFor(() => {
      expect(screen.getAllByRole("listitem")).toHaveLength(3);
    });

    const [calledUrl, calledInit] = (globalThis.fetch as ReturnType<typeof vi.fn>)
      .mock.calls[0];
    const calledParams = new URLSearchParams(
      String(calledUrl).split("?")[1],
    );
    expect(calledParams.get("before_id")).toBe("2");
    expect(calledParams.get("since")).toBe("2026-08-01T00:00:00.000000-03:00");
    expect(calledParams.get("until")).toBe("2026-08-15T23:59:59.999999-03:00");
    expect(calledInit).toEqual({ cache: "no-store" });
  });

  it("resets entries and cursor to page one when the initialHistory prop reference changes (design.md Decision 6, reused unchanged — a filter-driven navigation re-runs [id]/page.tsx's server fetch and produces exactly this new reference; no new reset logic exists in this component)", async () => {
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
      screen.getByRole("button", { name: /cargar más/i }),
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
      screen.queryByRole("button", { name: /cargar más/i }),
    ).not.toBeInTheDocument();
  });
});
