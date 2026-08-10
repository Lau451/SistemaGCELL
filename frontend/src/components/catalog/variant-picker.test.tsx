import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VariantPicker, type VariantPickerVariant } from "./variant-picker";

const NEGRO: VariantPickerVariant = {
  id: "v-negro",
  color: "negro",
  price: 15990,
  inStock: true,
  images: [{ url: "https://x.supabase.co/.../negro.jpg", alt: "Funda negra" }],
};

const TRANSPARENTE: VariantPickerVariant = {
  id: "v-transparente",
  color: "transparente",
  price: 12990,
  inStock: false,
  images: [{ url: "https://x.supabase.co/.../transparente.jpg", alt: "Funda transparente" }],
};

describe("VariantPicker", () => {
  let fetchSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    fetchSpy = vi.spyOn(globalThis, "fetch");
  });

  afterEach(() => {
    fetchSpy.mockRestore();
  });

  it("initializes with the first in-stock variant selected, not the first variant in array order", () => {
    render(<VariantPicker variants={[TRANSPARENTE, NEGRO]} />);

    // TRANSPARENTE (index 0) is out of stock, NEGRO (index 1) is in stock —
    // the in-stock one must win the default selection.
    expect(screen.getByTestId("variant-picker-price")).toHaveTextContent(/15\.990/);
    const negroSwatch = screen.getByRole("radio", { name: /negro/i });
    expect(negroSwatch).toHaveAttribute("aria-checked", "true");
  });

  it("keeps an out-of-stock swatch visible, clickable, and NOT disabled, with a Sin stock badge", () => {
    render(<VariantPicker variants={[NEGRO, TRANSPARENTE]} />);

    const outOfStockSwatch = screen.getByRole("radio", { name: /transparente/i });
    expect(outOfStockSwatch).toBeInTheDocument();
    expect(outOfStockSwatch).not.toBeDisabled();
    expect(outOfStockSwatch).not.toHaveAttribute("disabled");
    expect(outOfStockSwatch).toHaveTextContent(/sin stock/i);
  });

  it("swaps the displayed price and stock badge when an out-of-stock swatch is clicked, without any navigation or fetch", async () => {
    const user = userEvent.setup();
    render(<VariantPicker variants={[NEGRO, TRANSPARENTE]} />);

    // Starts on NEGRO (in stock): no stock badge next to the price.
    expect(screen.queryByTestId("variant-picker-stock-badge")).not.toBeInTheDocument();

    const outOfStockSwatch = screen.getByRole("radio", { name: /transparente/i });
    await user.click(outOfStockSwatch);

    expect(screen.getByTestId("variant-picker-price")).toHaveTextContent(/12\.990/);
    expect(screen.getByTestId("variant-picker-stock-badge")).toHaveTextContent(/sin stock/i);
    expect(outOfStockSwatch).toHaveAttribute("aria-checked", "true");
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("swaps back to an in-stock variant's price and hides the stock badge", async () => {
    const user = userEvent.setup();
    render(<VariantPicker variants={[NEGRO, TRANSPARENTE]} />);

    await user.click(screen.getByRole("radio", { name: /transparente/i }));
    await user.click(screen.getByRole("radio", { name: /^negro/i }));

    expect(screen.getByTestId("variant-picker-price")).toHaveTextContent(/15\.990/);
    expect(screen.queryByTestId("variant-picker-stock-badge")).not.toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("never calls fetch across mount and every interaction — all state is local", async () => {
    const user = userEvent.setup();
    render(<VariantPicker variants={[NEGRO, TRANSPARENTE]} />);

    expect(fetchSpy).not.toHaveBeenCalled();

    await user.click(screen.getByRole("radio", { name: /transparente/i }));
    await user.click(screen.getByRole("radio", { name: /^negro/i }));

    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("renders a radiogroup with one radio per variant", () => {
    render(<VariantPicker variants={[NEGRO, TRANSPARENTE]} />);

    expect(screen.getByRole("radiogroup")).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(2);
  });
});
