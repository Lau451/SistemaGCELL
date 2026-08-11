"use server";

/**
 * `signOutAction` — Server Action behind the admin layout's logout
 * control. Per `admin-authentication` spec's "Logout Clears The
 * Session": invalidates the session cookie via Supabase Auth's
 * `signOut()`, then returns the admin to `/admin/login`. Uses
 * `createSessionClient()` (PR2), the same session-writing factory the
 * login action uses — `signOut()` needs the same cookie-bound client to
 * clear the correct session.
 */
import { redirect } from "next/navigation";
import { createSessionClient } from "@/lib/supabase/server";

const ADMIN_LOGIN_PATH = "/admin/login";

export async function signOutAction(): Promise<void> {
  const supabase = await createSessionClient();
  await supabase.auth.signOut();
  redirect(ADMIN_LOGIN_PATH);
}
