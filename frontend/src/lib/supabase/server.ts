import "server-only";
import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";
import { getCatalogSupabaseEnv } from "./env";

/**
 * Two named factories over one internal builder — see
 * design.md "Decision: Two client factories, not one".
 *
 * `createAnonCatalogClient` is prerender-safe: it never calls `cookies()`,
 * so using it in a page does not opt the route into dynamic rendering and
 * does not silently kill `export const revalidate = 300`.
 *
 * `createRequestCatalogClient` is for Route Handlers (PR3): it awaits
 * `cookies()` once, then hands the library a *synchronous* adapter over
 * the already-resolved store, so Next's async `cookies()` never leaks
 * into `@supabase/ssr`'s adapter contract.
 *
 * Adapter shape verified against the installed `@supabase/ssr@0.12.4`
 * (`node_modules/@supabase/ssr/dist/module/types.d.ts`): the current,
 * non-deprecated `CookieMethodsServer` shape is `getAll` (required) +
 * `setAll` (optional) — not the deprecated `get`/`set`/`remove` trio.
 */

export function createAnonCatalogClient() {
  const { url, anonKey } = getCatalogSupabaseEnv();

  return createServerClient(url, anonKey, {
    cookies: {
      // No request context available at prerender time, and no auth yet:
      // an anon-key client has nothing to read from or write to cookies.
      getAll: () => [],
      setAll: () => {},
    },
  });
}

export async function createRequestCatalogClient() {
  const { url, anonKey } = getCatalogSupabaseEnv();
  const store = await cookies();

  return createServerClient(url, anonKey, {
    cookies: {
      getAll: () => store.getAll(),
      // No auth yet, so there is nothing to write back. Revisit once
      // authenticated routes land — see design.md open questions.
      setAll: () => {},
    },
  });
}

/**
 * Session-writing client for the admin auth flow (PR2/PR3) — the login
 * Server Action, Route Handlers under `/api/admin/*`, and Server
 * Components inside the `(admin)` group. Distinct from
 * `createAnonCatalogClient`/`createRequestCatalogClient` above (which
 * are read-only catalog clients and MUST NOT be reused for auth — see
 * spec.md "Requirement: Login With Email/Password").
 *
 * `setAll` best-effort writes cookies back through the awaited, already-
 * resolved `cookies()` store. Called from a Server Component (an RSC),
 * `store.set` throws because the store is read-only there — safe to
 * swallow: `proxy.ts` already refreshed the cookies for this request, so
 * an RSC-context write is redundant, not lossy.
 */
export async function createSessionClient() {
  const { url, anonKey } = getCatalogSupabaseEnv();
  const store = await cookies();

  return createServerClient(url, anonKey, {
    cookies: {
      getAll: () => store.getAll(),
      setAll: (cookiesToSet) => {
        try {
          for (const { name, value, options } of cookiesToSet) {
            store.set(name, value, options);
          }
        } catch {
          // Read-only store: called from an RSC. Safe to ignore — see
          // the doc comment above.
        }
      },
    },
  });
}
