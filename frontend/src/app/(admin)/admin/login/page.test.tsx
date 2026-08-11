import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

/**
 * `/admin/login` page — thin Server Component wiring: reads the `next`
 * search param and hands it straight to `LoginForm` (already tested in
 * isolation by `login-form.test.tsx`) without re-verifying form
 * internals here. `LoginForm` is stubbed so this proves ONLY the
 * searchParams → prop extraction, including the `string[] | undefined`
 * shape Next's `searchParams` type allows.
 */

vi.mock("./login-form", () => ({
  LoginForm: ({ next }: { next: string | null }) => (
    <div data-testid="login-form-next">{next === null ? "null" : next}</div>
  ),
}));

async function importPage() {
  const mod = await import("./page");
  return mod.default;
}

describe("LoginPage", () => {
  it("passes a string `next` search param through to LoginForm", async () => {
    const LoginPage = await importPage();
    const jsx = await LoginPage({
      searchParams: Promise.resolve({ next: "/admin/products" }),
    });
    render(jsx);

    expect(screen.getByTestId("login-form-next")).toHaveTextContent(
      "/admin/products",
    );
  });

  it("passes null when no `next` search param is present", async () => {
    const LoginPage = await importPage();
    const jsx = await LoginPage({ searchParams: Promise.resolve({}) });
    render(jsx);

    expect(screen.getByTestId("login-form-next")).toHaveTextContent("null");
  });

  it("passes null when `next` arrives as an array (malformed query)", async () => {
    const LoginPage = await importPage();
    const jsx = await LoginPage({
      searchParams: Promise.resolve({ next: ["/admin", "/admin/products"] }),
    });
    render(jsx);

    expect(screen.getByTestId("login-form-next")).toHaveTextContent("null");
  });
});
