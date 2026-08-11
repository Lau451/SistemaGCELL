import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `signInAction` — Server Action backing the login form's
 * `useActionState` wiring. Per `admin-authentication` spec's "Invalid
 * credentials are rejected" scenario: on failure the caller MUST see
 * only a generic message, never Supabase's own error text (which would
 * leak whether the email exists). `createSessionClient` and
 * `next/navigation`'s `redirect` are mocked so this proves the
 * error-genericization and safe-redirect branching without a live
 * Supabase Auth service.
 *
 * @see design.md "Login / logout", "Open-redirect guard"
 */

const SIGN_IN_WITH_PASSWORD = vi.fn();
const REDIRECT = vi.fn();

vi.mock("@/lib/supabase/server", () => ({
  createSessionClient: vi.fn(async () => ({
    auth: { signInWithPassword: SIGN_IN_WITH_PASSWORD },
  })),
}));

vi.mock("next/navigation", () => ({
  redirect: REDIRECT,
}));

async function importAction() {
  const mod = await import("./actions");
  return mod.signInAction;
}

function formDataFor(fields: Record<string, string>) {
  const data = new FormData();
  for (const [key, value] of Object.entries(fields)) {
    data.set(key, value);
  }
  return data;
}

describe("signInAction", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("returns a generic error and never redirects when Supabase rejects the credentials", async () => {
    SIGN_IN_WITH_PASSWORD.mockResolvedValue({
      error: { message: "Invalid login credentials" },
    });

    const signInAction = await importAction();
    const result = await signInAction(
      { error: null },
      formDataFor({ email: "admin@gcell.local", password: "wrong-pass" }),
    );

    expect(result.error).toBeTruthy();
    expect(result.error).not.toContain("Invalid login credentials");
    expect(REDIRECT).not.toHaveBeenCalled();
  });

  it("returns the SAME generic message for a nonexistent email (no oracle)", async () => {
    SIGN_IN_WITH_PASSWORD.mockResolvedValue({
      error: { message: "User not found" },
    });

    const signInAction = await importAction();
    const wrongPasswordResult = await signInAction(
      { error: null },
      formDataFor({ email: "admin@gcell.local", password: "wrong-pass" }),
    );

    SIGN_IN_WITH_PASSWORD.mockResolvedValue({
      error: { message: "User not found" },
    });
    const noSuchUserResult = await signInAction(
      { error: null },
      formDataFor({ email: "nobody@gcell.local", password: "whatever" }),
    );

    expect(noSuchUserResult.error).toBe(wrongPasswordResult.error);
  });

  it("redirects to the safe `next` path on successful sign-in", async () => {
    SIGN_IN_WITH_PASSWORD.mockResolvedValue({ error: null });

    const signInAction = await importAction();
    await signInAction(
      { error: null },
      formDataFor({
        email: "admin@gcell.local",
        password: "correct-pass",
        next: "/admin/products",
      }),
    );

    expect(REDIRECT).toHaveBeenCalledWith("/admin/products");
  });

  it("redirects to /admin when `next` is unsafe on successful sign-in", async () => {
    SIGN_IN_WITH_PASSWORD.mockResolvedValue({ error: null });

    const signInAction = await importAction();
    await signInAction(
      { error: null },
      formDataFor({
        email: "admin@gcell.local",
        password: "correct-pass",
        next: "https://evil.example.com",
      }),
    );

    expect(REDIRECT).toHaveBeenCalledWith("/admin");
  });
});
