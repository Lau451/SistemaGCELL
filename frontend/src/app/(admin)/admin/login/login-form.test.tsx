import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `LoginForm` — client component wiring `signInAction` through React 19's
 * `useActionState`. `signInAction` itself is mocked (already covered in
 * isolation by `actions.test.ts`) so this proves the FORM's own
 * responsibility: labeled inputs, submitting via the action, and
 * rendering the returned generic error — never the plumbing already
 * proven elsewhere.
 */

const SIGN_IN_ACTION = vi.fn();

vi.mock("./actions", () => ({
  signInAction: (...args: unknown[]) => SIGN_IN_ACTION(...args),
}));

async function importLoginForm() {
  const mod = await import("./login-form");
  return mod.LoginForm;
}

describe("LoginForm", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("renders labeled email and password inputs and a submit button", async () => {
    const LoginForm = await importLoginForm();
    render(<LoginForm next={null} />);

    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/contraseña/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /ingresar/i }),
    ).toBeInTheDocument();
  });

  it("submits the typed credentials and shows the generic error the action returns", async () => {
    SIGN_IN_ACTION.mockResolvedValue({ error: "Email o contraseña incorrectos." });
    const user = userEvent.setup();

    const LoginForm = await importLoginForm();
    render(<LoginForm next="/admin/products" />);

    await user.type(screen.getByLabelText(/email/i), "admin@gcell.local");
    await user.type(screen.getByLabelText(/contraseña/i), "wrong-pass");
    await user.click(screen.getByRole("button", { name: /ingresar/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        "Email o contraseña incorrectos.",
      );
    });

    expect(SIGN_IN_ACTION).toHaveBeenCalled();
    const [, formData] = SIGN_IN_ACTION.mock.calls[0] as [unknown, FormData];
    expect(formData.get("email")).toBe("admin@gcell.local");
    expect(formData.get("next")).toBe("/admin/products");
  });
});
