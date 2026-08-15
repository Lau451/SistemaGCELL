import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `ProductForm` — client component shared by create (`new/page.tsx`) and
 * edit (`[id]/page.tsx`), wiring whichever action is passed in through
 * React 19's `useActionState`. `retireVariantAction` is mocked (already
 * covered in isolation by `actions.test.ts`) so this proves the FORM's
 * own responsibilities: labeled inputs, no slug field ever, adding a
 * variant row, removing an unsaved row client-only (no request), and
 * removing a saved row submitting the retire action.
 *
 * @see design.md "Frontend relay" (variant row shape), tasks.md 4.10
 */

const RETIRE_VARIANT_ACTION = vi.fn();

vi.mock("./actions", () => ({
  retireVariantAction: (...args: unknown[]) => RETIRE_VARIANT_ACTION(...args),
}));

async function importProductForm() {
  const mod = await import("./product-form");
  return mod.ProductForm;
}

describe("ProductForm", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("renders labeled name/model inputs and never a slug field", async () => {
    const stubAction = vi.fn().mockResolvedValue({ error: null });
    const ProductForm = await importProductForm();

    render(
      <ProductForm
        action={stubAction}
        submitLabel="Create product"
      />,
    );

    expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/model/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/slug/i)).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue(/slug/i)).not.toBeInTheDocument();
  });

  it("adds a new, unsaved variant row on demand", async () => {
    const stubAction = vi.fn().mockResolvedValue({ error: null });
    const user = userEvent.setup();
    const ProductForm = await importProductForm();

    render(<ProductForm action={stubAction} submitLabel="Create product" />);

    expect(screen.queryAllByLabelText(/color/i)).toHaveLength(0);

    await user.click(screen.getByRole("button", { name: /add variant/i }));

    expect(screen.getAllByLabelText(/color/i)).toHaveLength(1);
  });

  it("removes an UNSAVED row client-only, with no retire request", async () => {
    const stubAction = vi.fn().mockResolvedValue({ error: null });
    const user = userEvent.setup();
    const ProductForm = await importProductForm();

    render(<ProductForm action={stubAction} submitLabel="Create product" />);

    await user.click(screen.getByRole("button", { name: /add variant/i }));
    expect(screen.getAllByLabelText(/color/i)).toHaveLength(1);

    await user.click(screen.getByRole("button", { name: /remove/i }));

    expect(screen.queryAllByLabelText(/color/i)).toHaveLength(0);
    expect(RETIRE_VARIANT_ACTION).not.toHaveBeenCalled();
  });

  it("removes a SAVED row by submitting retireVariantAction", async () => {
    RETIRE_VARIANT_ACTION.mockResolvedValue(undefined);
    const stubAction = vi.fn().mockResolvedValue({ error: null });
    const user = userEvent.setup();
    const ProductForm = await importProductForm();

    render(
      <ProductForm
        action={stubAction}
        submitLabel="Save changes"
        productId="p1"
        initialName="Funda iPhone 15"
        initialModel="iPhone 15"
        initialVariants={[
          { id: "v1", color: "negro", price: "5000.00", cost: "2000.00" },
        ]}
      />,
    );

    expect(screen.getByLabelText(/color/i)).toHaveValue("negro");

    await user.click(screen.getByRole("button", { name: /remove/i }));

    await waitFor(() => {
      expect(RETIRE_VARIANT_ACTION).toHaveBeenCalledTimes(1);
    });
    const [formData] = RETIRE_VARIANT_ACTION.mock.calls[0] as [FormData];
    expect(formData.get("product-id")).toBe("p1");
    expect(formData.get("variant-id")).toBe("v1");

    await waitFor(() => {
      expect(screen.queryAllByLabelText(/color/i)).toHaveLength(0);
    });
  });

  it("renders the error returned by the action with role=alert", async () => {
    const stubAction = vi
      .fn()
      .mockResolvedValue({ error: "Field required" });
    const user = userEvent.setup();
    const ProductForm = await importProductForm();

    render(<ProductForm action={stubAction} submitLabel="Create product" />);

    await user.type(screen.getByLabelText(/name/i), "Funda iPhone 15");
    await user.type(screen.getByLabelText(/model/i), "iPhone 15");
    await user.click(
      screen.getByRole("button", { name: /create product/i }),
    );

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent("Field required");
    });
  });

  it("renders an Initial quantity input for a new row in CREATE mode (no productId)", async () => {
    const stubAction = vi.fn().mockResolvedValue({ error: null });
    const user = userEvent.setup();
    const ProductForm = await importProductForm();

    render(<ProductForm action={stubAction} submitLabel="Create product" />);

    await user.click(screen.getByRole("button", { name: /add variant/i }));

    expect(screen.getByLabelText(/initial quantity/i)).toBeInTheDocument();
  });

  it("never renders Initial quantity for an existing (already-saved) row", async () => {
    const stubAction = vi.fn().mockResolvedValue({ error: null });
    const ProductForm = await importProductForm();

    render(
      <ProductForm
        action={stubAction}
        submitLabel="Save changes"
        productId="p1"
        initialName="Funda iPhone 15"
        initialModel="iPhone 15"
        initialVariants={[
          { id: "v1", color: "negro", price: "5000.00", cost: "2000.00" },
        ]}
      />,
    );

    expect(screen.queryByLabelText(/initial quantity/i)).not.toBeInTheDocument();
  });

  it("never renders Initial quantity for a new row added on the EDIT page (productId present)", async () => {
    const stubAction = vi.fn().mockResolvedValue({ error: null });
    const user = userEvent.setup();
    const ProductForm = await importProductForm();

    render(
      <ProductForm action={stubAction} submitLabel="Save changes" productId="p1" />,
    );

    await user.click(screen.getByRole("button", { name: /add variant/i }));

    expect(screen.queryByLabelText(/initial quantity/i)).not.toBeInTheDocument();
  });

  it("uses number inputs with step=0.01 and min=0 for price and cost", async () => {
    const stubAction = vi.fn().mockResolvedValue({ error: null });
    const user = userEvent.setup();
    const ProductForm = await importProductForm();

    render(<ProductForm action={stubAction} submitLabel="Create product" />);
    await user.click(screen.getByRole("button", { name: /add variant/i }));

    const priceInput = screen.getByLabelText(/price/i);
    const costInput = screen.getByLabelText(/cost/i);

    expect(priceInput).toHaveAttribute("type", "number");
    expect(priceInput).toHaveAttribute("step", "0.01");
    expect(priceInput).toHaveAttribute("min", "0");
    expect(costInput).toHaveAttribute("type", "number");
    expect(costInput).toHaveAttribute("step", "0.01");
    expect(costInput).toHaveAttribute("min", "0");
  });
});
