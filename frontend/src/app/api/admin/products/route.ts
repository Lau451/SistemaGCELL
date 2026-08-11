/**
 * `GET /api/admin/products` — server-to-server proxy Route Handler.
 * `proxy.ts` already gates unauthenticated *page* visits, but this route
 * is deliberately OUTSIDE `proxy.ts`'s `/admin/:path*` matcher (see
 * design.md "Decision: admin routes live at `app/(admin)/admin/**`" —
 * `/api/admin/*` returns its own `401` JSON instead of an HTML redirect),
 * so it repeats the session check itself.
 *
 * This check is a routing optimization only, never the trust boundary:
 * FastAPI's `verify_admin_jwt` re-verifies the token's signature/exp/
 * iss/aud on every request regardless (design.md "Technical Approach").
 * A forged or stale cookie buys nothing here — it just fails later, at
 * the real boundary — but short-circuiting BEFORE calling `fetch` still
 * matters: it saves a wasted upstream round-trip and matches the
 * `admin-api-access` spec's "never reaches the repository" requirement
 * mirrored at this layer.
 *
 * `getClaims()` (server-validated) gates the request; `getSession()` is
 * read only afterwards, purely to extract the opaque `access_token` to
 * relay — never trusted as an authorization decision on its own (see
 * design.md "Decision: `getClaims()` for the gate, `getSession()` only
 * to extract the token").
 *
 * @see design.md "`GET /api/admin/products`"
 */
import { NextResponse } from "next/server";
import { getBackendUrl } from "@/lib/admin/env";
import { createSessionClient } from "@/lib/supabase/server";

function unauthenticated() {
  return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
}

export async function GET() {
  const supabase = await createSessionClient();

  const { data: claimsData, error: claimsError } =
    await supabase.auth.getClaims();
  if (claimsError || !claimsData?.claims) {
    return unauthenticated();
  }

  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session) {
    return unauthenticated();
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${getBackendUrl()}/admin/products`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      { error: "backend_unavailable" },
      { status: 502 },
    );
  }

  return NextResponse.json(await upstream.json(), {
    status: upstream.status,
    headers: { "Cache-Control": "private, no-store" },
  });
}
