"use server";

/**
 * `signInAction` — Server Action wired to the login form's
 * `useActionState` hook (see `login-form.tsx`). Uses
 * `createSessionClient()` (PR2), never the read-only catalog factories
 * — see `admin-authentication` spec's "Login With Email/Password"
 * requirement.
 *
 * On failure, the caller NEVER sees Supabase's own error message: the
 * spec's "Invalid credentials are rejected" scenario requires a single
 * generic indication regardless of whether the email exists, the
 * password is wrong, or the account is unconfirmed — distinguishing any
 * of those would leak account existence to an attacker (the same
 * "no-oracle" posture the backend's `verify_admin_jwt` already applies
 * to token-verification failures).
 *
 * On success, `redirect()`s to the `next` field IF it passes
 * `isSafeAdminPath` (open-redirect guard, PR2), else to the default
 * admin landing page — per design.md's "Open-redirect guard" section.
 */
import { redirect } from "next/navigation";
import { isSafeAdminPath } from "@/lib/admin/redirect";
import { createSessionClient } from "@/lib/supabase/server";

const GENERIC_SIGN_IN_ERROR = "Email o contraseña incorrectos.";
const ADMIN_LANDING_PATH = "/admin";

export interface SignInState {
  error: string | null;
}

function resolveRedirectTarget(next: FormDataEntryValue | null): string {
  const candidate = typeof next === "string" ? next : null;
  return isSafeAdminPath(candidate) ? candidate! : ADMIN_LANDING_PATH;
}

export async function signInAction(
  _prevState: SignInState,
  formData: FormData,
): Promise<SignInState> {
  const email = String(formData.get("email") ?? "");
  const password = String(formData.get("password") ?? "");

  const supabase = await createSessionClient();
  const { error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });

  if (error) {
    return { error: GENERIC_SIGN_IN_ERROR };
  }

  redirect(resolveRedirectTarget(formData.get("next")));
}
