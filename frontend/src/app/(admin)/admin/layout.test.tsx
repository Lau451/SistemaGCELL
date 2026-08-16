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

vi.mock("./actions", () => ({
  signOutAction: (...args: unknown[]) => SIGN_OUT_ACTION(...args),
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

    expect(screen.getByRole("link", { name: /products/i })).toHaveAttribute(
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

  it("invokes signOutAction when the sign-out control is submitted", async () => {
    SIGN_OUT_ACTION.mockResolvedValue(undefined);
    const user = userEvent.setup();

    const AdminLayout = await importLayout();
    render(<AdminLayout>{<p>Landing content</p>}</AdminLayout>);

    await user.click(screen.getByRole("button", { name: /sign out/i }));

    expect(SIGN_OUT_ACTION).toHaveBeenCalledTimes(1);
  });
});
