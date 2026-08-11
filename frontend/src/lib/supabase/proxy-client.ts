import "server-only";
import type { NextRequest, NextResponse } from "next/server";
import { createServerClient } from "@supabase/ssr";
import { getCatalogSupabaseEnv } from "./env";

/**
 * Request/response cookie-pair client factory for use exclusively inside
 * `proxy.ts` (Next 16's renamed `middleware.ts` convention — proxy runs
 * once per matched request, ahead of routing).
 *
 * Adapter shape verified against the installed `@supabase/ssr@0.12.4`
 * (`node_modules/@supabase/ssr/dist/module/types.d.ts`): `setAll` takes
 * a SECOND argument, `headers: Record<string, string>`, carrying
 * cache-suppressing headers (`Cache-Control`, `Expires`, `Pragma`) that
 * the library sends whenever it writes auth cookies. Both the cookies
 * AND those headers MUST be applied to the response — omitting the
 * headers means a CDN or reverse proxy could cache and serve one user's
 * session to a different user. This is a correctness requirement, not a
 * style preference (see the type's own doc comment and design.md's
 * "Cookie adapter" section).
 *
 * Cookies are written to BOTH `request.cookies` (so any code reading the
 * request further down this same proxy invocation sees the refreshed
 * values) and `response.cookies` (so the browser receives them).
 */
export function createProxyClient(
  request: NextRequest,
  response: NextResponse,
) {
  const { url, anonKey } = getCatalogSupabaseEnv();

  return createServerClient(url, anonKey, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (cookiesToSet, headers) => {
        for (const { name, value, options } of cookiesToSet) {
          request.cookies.set(name, value);
          response.cookies.set(name, value, options);
        }
        for (const [key, value] of Object.entries(headers)) {
          response.headers.set(key, value);
        }
      },
    },
  });
}
