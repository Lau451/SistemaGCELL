import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `signOutAction` — Server Action behind the admin layout's logout
 * control. Per `admin-authentication` spec's "Logout Clears The
 * Session": clears the session cookie via Supabase Auth's `signOut()`,
 * then returns the admin to the login page. `createSessionClient` and
 * `next/navigation`'s `redirect` are mocked to prove the call order
 * without a live Supabase Auth service.
 *
 * @see design.md "Login / logout"
 */

const SIGN_OUT = vi.fn();
const REDIRECT = vi.fn();

vi.mock("@/lib/supabase/server", () => ({
  createSessionClient: vi.fn(async () => ({
    auth: { signOut: SIGN_OUT },
  })),
}));

vi.mock("next/navigation", () => ({
  redirect: REDIRECT,
}));

async function importAction() {
  const mod = await import("./actions");
  return mod.signOutAction;
}

describe("signOutAction", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("calls Supabase signOut before redirecting to /admin/login", async () => {
    SIGN_OUT.mockResolvedValue({ error: null });
    const callOrder: string[] = [];
    SIGN_OUT.mockImplementation(async () => {
      callOrder.push("signOut");
      return { error: null };
    });
    REDIRECT.mockImplementation((path: string) => {
      callOrder.push(`redirect:${path}`);
    });

    const signOutAction = await importAction();
    await signOutAction();

    expect(SIGN_OUT).toHaveBeenCalledTimes(1);
    expect(callOrder).toEqual(["signOut", "redirect:/admin/login"]);
  });
});
