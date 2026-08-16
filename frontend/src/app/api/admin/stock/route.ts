/**
 * `GET /api/admin/stock` — proxy Route Handler for the catalog-wide stock
 * triage page (`(admin)/admin/stock/page.tsx`). Relays to the backend's
 * `GET /admin/stock`, mirroring the auth-gate-then-relay pattern already
 * used by every other admin proxy.
 *
 * This route mirrors the movements proxy
 * (`[id]/variants/[variantId]/stock/movements/route.ts`), not the products
 * proxy (`api/admin/products/route.ts`), because it must read query params:
 * only `below` and `search` are forwarded, rebuilt into a fresh
 * `URLSearchParams` — NEVER `new URL(request.url).search` verbatim, which
 * would let a client inject arbitrary params into the backend URL
 * (design.md Decision 5).
 *
 * @see design.md "Data Flow" (READ), "Decision 5"
 */
import { NextResponse } from "next/server";
import { adminBackendFetch } from "@/lib/admin/backend-fetch";

const NO_STORE_HEADERS = { "Cache-Control": "private, no-store" } as const;
const ALLOWED_QUERY_PARAMS = ["below", "search"] as const;

export async function GET(request: Request) {
  const incoming = new URL(request.url).searchParams;
  const outgoing = new URLSearchParams();
  for (const key of ALLOWED_QUERY_PARAMS) {
    const value = incoming.get(key);
    if (value !== null) {
      outgoing.set(key, value);
    }
  }
  const query = outgoing.toString();
  const path = `/admin/stock${query ? `?${query}` : ""}`;

  const result = await adminBackendFetch(path);

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
    headers: NO_STORE_HEADERS,
  });
}
