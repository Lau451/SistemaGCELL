import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { createProxyClient } from "@/lib/supabase/proxy-client";
import { isSafeAdminPath } from "@/lib/admin/redirect";

/**
 * Next 16's renamed `middleware.ts` file convention (see design.md
 * "Decision: `proxy.ts`, not `middleware.ts`"). Refreshes the Supabase
 * session and gates every `/admin/*` request. `/api/admin/*` is
 * deliberately outside the matcher below — a JSON fetch getting
 * redirected to an HTML login page is a bug; that path returns its own
 * `401` later, in the Route Handler (PR3), never here.
 *
 * Uses `getClaims()` for the pass/fail gate, never `getSession()` — a
 * session read over cookies is explicitly untrustworthy
 * (`auth-js/GoTrueClient.d.ts:1413`). This proxy never needs the raw
 * access token, only the boolean "is this session valid" answer, so
 * `getSession()` is not called here at all (it is only read later, in
 * the Route Handler, purely as an opaque string to relay).
 */

const ADMIN_LOGIN_PATH = "/admin/login";
const ADMIN_LANDING_PATH = "/admin";

// Cache-suppressing headers `@supabase/ssr`'s `setAll` passes alongside
// a cookie refresh (see `lib/supabase/proxy-client.ts`). When the
// request is ultimately answered with a *redirect* response rather than
// the pass-through `response` object that `createProxyClient` wrote
// them onto, they must be carried over by hand or a mid-visit token
// refresh would be silently dropped.
const SESSION_REFRESH_HEADER_NAMES = ["cache-control", "expires", "pragma"];

function carryRefreshedSession(
  source: NextResponse,
  target: NextResponse,
): NextResponse {
  for (const cookie of source.cookies.getAll()) {
    target.cookies.set(cookie);
  }
  for (const name of SESSION_REFRESH_HEADER_NAMES) {
    const value = source.headers.get(name);
    if (value) {
      target.headers.set(name, value);
    }
  }
  return target;
}

export async function proxy(request: NextRequest) {
  const response = NextResponse.next({ request });
  const supabase = createProxyClient(request, response);

  const { data, error } = await supabase.auth.getClaims();
  const isAuthenticated = !error && Boolean(data?.claims);

  const { pathname, search } = request.nextUrl;

  if (pathname === ADMIN_LOGIN_PATH) {
    if (!isAuthenticated) {
      // Render the form; carries any refreshed-then-invalidated cookie
      // state through unchanged.
      return response;
    }
    return carryRefreshedSession(
      response,
      NextResponse.redirect(new URL(ADMIN_LANDING_PATH, request.url)),
    );
  }

  if (!isAuthenticated) {
    const loginUrl = new URL(ADMIN_LOGIN_PATH, request.url);
    const next = `${pathname}${search}`;
    if (isSafeAdminPath(next)) {
      loginUrl.searchParams.set("next", next);
    }
    return carryRefreshedSession(response, NextResponse.redirect(loginUrl));
  }

  return response;
}

export const config = {
  matcher: ["/admin/:path*"],
};
