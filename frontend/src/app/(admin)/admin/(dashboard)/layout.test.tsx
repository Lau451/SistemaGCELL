import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `AdminLayout` — shell wrapping all `/admin/*` pages: renders children,
 * a nav link to the products proof page, and the logout control wired to
 * `signOutAction` (already unit-tested in isolation by
 * `actions.test.ts`) — this proves ONLY the shell's own wiring: children
 * pass through, and submitting the logout form invokes the action.
 */

const SIGN_OUT_ACTION = vi.fn();

vi.mock("../actions", () => ({
  signOutAction: (...args: unknown[]) => SIGN_OUT_ACTION(...args),
}));

// `StockAlertBadge` is an async Server Component; RTL cannot client-render
// one under `Suspense` (design.md "Testing Strategy"), so it is stubbed
// with a synchronous marker to prove only the layout's own wiring.
vi.mock("./stock-alert-badge", () => ({
  StockAlertBadge: () => <span>BADGE_STUB</span>,
}));

async function importLayout() {
  const mod = await import("./layout");
  return mod.default;
}

describe("AdminLayout", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("renders the wrapped children", async () => {
    const AdminLayout = await importLayout();
    render(<AdminLayout>{<p>Landing content</p>}</AdminLayout>);

    expect(screen.getByText("Landing content")).toBeInTheDocument();
  });

  it("links to the products proof page", async () => {
    const AdminLayout = await importLayout();
    render(<AdminLayout>{<p>Landing content</p>}</AdminLayout>);

    expect(screen.getByRole("link", { name: /productos/i })).toHaveAttribute(
      "href",
      "/admin/products",
    );
  });

  it("links to the stock triage page", async () => {
    const AdminLayout = await importLayout();
    render(<AdminLayout>{<p>Landing content</p>}</AdminLayout>);

    expect(screen.getByRole("link", { name: /stock/i })).toHaveAttribute(
      "href",
      "/admin/stock",
    );
  });

  it("renders the low-stock badge inside the Stock link", async () => {
    const AdminLayout = await importLayout();
    render(<AdminLayout>{<p>Landing content</p>}</AdminLayout>);

    const stockLink = screen.getByRole("link", { name: /stock/i });
    expect(
      screen.getByText("BADGE_STUB").closest("a"),
    ).toBe(stockLink);
  });

  it("invokes signOutAction when the sign-out control is submitted", async () => {
    SIGN_OUT_ACTION.mockResolvedValue(undefined);
    const user = userEvent.setup();

    const AdminLayout = await importLayout();
    render(<AdminLayout>{<p>Landing content</p>}</AdminLayout>);

    await user.click(screen.getByRole("button", { name: /cerrar sesión/i }));

    expect(SIGN_OUT_ACTION).toHaveBeenCalledTimes(1);
  });
});
