/**
 * `adminBackendFetch` — the ONE session-gate-then-relay implementation
 * used by every server-only caller that talks to FastAPI's `/admin/*`
 * router: the read Route Handlers (`route.ts`, `[id]/route.ts`) AND the
 * write Server Actions (`actions.ts`). Centralizing this here is
 * design.md's "Decision: no write Route Handlers — Server Actions relay
 * directly" — the proposal's original "session-gate, then relay with a
 * Bearer token" intent, now implemented once instead of duplicated.
 *
 * `getClaims()` (server-validated) gates the call — `fetch` is NEVER
 * invoked without claims, mirroring the `admin-api-access` spec's "never
 * reaches the repository" posture already proven at the route layer.
 * `getSession().access_token` is read only AFTERWARDS, purely to relay —
 * never trusted as an authorization decision on its own (same posture as
 * `admin-panel-auth`'s "`getClaims()` for the gate, `getSession()` only
 * to extract the token").
 *
 * This helper must NOT call `.json()` unconditionally: a `204` (both
 * `DELETE` routes) has no body, and calling `.json()` on it throws.
 *
 * @see design.md "Frontend relay"
 */
import { getBackendUrl } from "@/lib/admin/env";
import { createSessionClient } from "@/lib/supabase/server";

export type AdminBackendResult =
  | { outcome: "response"; status: number; body: unknown }
  | { outcome: "unauthenticated" }
  | { outcome: "backend_unavailable" };

export interface AdminBackendFetchInit {
  method?: string;
  body?: unknown;
}

export async function adminBackendFetch(
  path: string,
  init?: AdminBackendFetchInit,
): Promise<AdminBackendResult> {
  const supabase = await createSessionClient();

  const { data: claimsData, error: claimsError } =
    await supabase.auth.getClaims();
  if (claimsError || !claimsData?.claims) {
    return { outcome: "unauthenticated" };
  }

  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    return { outcome: "unauthenticated" };
  }

  const hasBody = init?.body !== undefined;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${session.access_token}`,
  };
  if (hasBody) {
    headers["Content-Type"] = "application/json";
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${getBackendUrl()}${path}`, {
      method: init?.method ?? "GET",
      headers,
      // Money never becomes a JS `number` anywhere in this call: the
      // caller's `body` already carries price/cost as the exact string
      // `FormData` produced (see `actions.ts`'s `buildVariantsPayload`),
      // and `JSON.stringify` on a string value is lossless — never a
      // `parseFloat`/`Number()` round-trip (design.md's money-precision
      // threat-matrix item).
      body: hasBody ? JSON.stringify(init.body) : undefined,
      cache: "no-store",
    });
  } catch {
    return { outcome: "backend_unavailable" };
  }

  // A 204 (both retire routes) has no body — calling `.json()` on it
  // throws, so it must be special-cased rather than called unconditionally.
  const body = upstream.status === 204 ? null : await upstream.json();
  return { outcome: "response", status: upstream.status, body };
}
