import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `StockManager` — client component rendered on the product detail page
 * (`[id]/page.tsx`), the sole UI surface for `recordStockMovementAction`.
 * `./actions` and `next/navigation` are mocked following
 * `image-manager.test.tsx`'s exact convention.
 */

const RECORD_ACTION = vi.fn();
const ROUTER_REFRESH = vi.fn();

vi.mock("./actions", () => ({
  recordStockMovementAction: (...args: unknown[]) => RECORD_ACTION(...args),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: ROUTER_REFRESH }),
}));

async function importStockManager() {
  const mod = await import("./stock-manager");
  return mod.StockManager;
}

const STOCK = [
  { variant_id: "v1", color: "negro", quantity_on_hand: 5 },
  { variant_id: "v2", color: "rojo", quantity_on_hand: 0 },
];

describe("StockManager", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("renders each variant row with its current quantity", async () => {
    const StockManager = await importStockManager();

    render(<StockManager productId="p1" initialStock={STOCK} />);

    expect(
      screen.getByText("negro", { selector: "span.font-medium" }),
    ).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(
      screen.getByText("rojo", { selector: "span.font-medium" }),
    ).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("labels only the zero-quantity variant as out of stock", async () => {
    const StockManager = await importStockManager();

    render(<StockManager productId="p1" initialStock={STOCK} />);

    // Exactly one "Sin stock" label exists (getByText throws on 0 or 2+
    // matches), proving the zero-quantity variant is the ONLY one flagged.
    expect(screen.getByText(/sin stock/i)).toBeInTheDocument();

    const negroRow = screen
      .getByText("negro", { selector: "span.font-medium" })
      .closest("div");
    expect(negroRow?.textContent).not.toMatch(/sin stock/i);
  });

  it("shows the direction control only when movement type is adjustment", async () => {
    const user = userEvent.setup();
    const StockManager = await importStockManager();

    render(<StockManager productId="p1" initialStock={STOCK} />);

    expect(screen.queryByLabelText(/dirección/i)).not.toBeInTheDocument();

    await user.selectOptions(
      screen.getByLabelText(/tipo de movimiento/i),
      "adjustment",
    );

    expect(screen.getByLabelText(/dirección/i)).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText(/tipo de movimiento/i), "sale");

    expect(screen.queryByLabelText(/dirección/i)).not.toBeInTheDocument();
  });

  it("submits recordStockMovementAction bound to the productId with the selected fields", async () => {
    RECORD_ACTION.mockResolvedValue({ error: null });
    const user = userEvent.setup();
    const StockManager = await importStockManager();

    render(<StockManager productId="p1" initialStock={STOCK} />);

    await user.selectOptions(screen.getByLabelText(/^variante$/i), "v2");
    await user.selectOptions(
      screen.getByLabelText(/tipo de movimiento/i),
      "restock",
    );
    await user.type(screen.getByLabelText(/cantidad/i), "10");
    await user.click(screen.getByRole("button", { name: /registrar movimiento/i }));

    await waitFor(() => {
      expect(RECORD_ACTION).toHaveBeenCalledTimes(1);
    });
    const [productId, , formData] = RECORD_ACTION.mock.calls[0] as [
      string,
      unknown,
      FormData,
    ];
    expect(productId).toBe("p1");
    expect(formData.get("variant-id")).toBe("v2");
    expect(formData.get("movement-type")).toBe("restock");
    expect(formData.get("magnitude")).toBe("10");
  });

  it("refreshes the router after a successful submission", async () => {
    RECORD_ACTION.mockResolvedValue({ error: null });
    const user = userEvent.setup();
    const StockManager = await importStockManager();

    render(<StockManager productId="p1" initialStock={STOCK} />);

    await user.type(screen.getByLabelText(/cantidad/i), "3");
    await user.click(screen.getByRole("button", { name: /registrar movimiento/i }));

    await waitFor(() => {
      expect(ROUTER_REFRESH).toHaveBeenCalledTimes(1);
    });
  });

  it("surfaces a submission error via role=alert", async () => {
    RECORD_ACTION.mockResolvedValue({ error: "Unknown movement type" });
    const user = userEvent.setup();
    const StockManager = await importStockManager();

    render(<StockManager productId="p1" initialStock={STOCK} />);

    await user.type(screen.getByLabelText(/cantidad/i), "3");
    await user.click(screen.getByRole("button", { name: /registrar movimiento/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Unknown movement type",
      );
    });
    expect(ROUTER_REFRESH).not.toHaveBeenCalled();
  });
});
