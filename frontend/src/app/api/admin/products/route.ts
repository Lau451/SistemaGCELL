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
 * Refactored (PR4) onto the shared `adminBackendFetch` relay — the same
 * gate-then-relay logic, now centralized in `lib/admin/backend-fetch.ts`
 * so the write Server Actions (`actions.ts`) don't duplicate it. This is
 * a read-only extension: still GET-only, no POST added here (writes go
 * exclusively through Server Actions — design.md "Decision: no write
 * Route Handlers").
 *
 * @see design.md "`GET /api/admin/products`", "Frontend relay"
 */
import { NextResponse } from "next/server";
import { adminBackendFetch } from "@/lib/admin/backend-fetch";

export async function GET() {
  const result = await adminBackendFetch("/admin/products");

  if (result.outcome === "unauthenticated") {
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });
  }

  if (result.outcome === "backend_unavailable") {
    return NextResponse.json(
      { error: "backend_unavailable" },
      { status: 502 },
    );
  }

  return NextResponse.json(result.body, {
    status: result.status,
    headers: { "Cache-Control": "private, no-store" },
  });
}
