/**
 * `GET /api/admin/products/[id]/variants/[variantId]/stock/movements` —
 * proxy Route Handler used by `stock-history.tsx` (initial server prefetch
 * via `[id]/page.tsx`'s `fetchAdminProductStockHistory`, and client-side
 * "Load more"/variant-switch fetches) to read a variant's paginated stock
 * movement history. Relays to the backend's
 * `GET /admin/products/{id}/variants/{variantId}/stock/movements`,
 * mirroring the EXACT auth-gate-then-relay pattern already used by the
 * sibling `[id]/stock/route.ts` proxy.
 *
 * Only `limit` and `before_id` are forwarded, rebuilt into a fresh
 * `URLSearchParams` — NEVER `new URL(request.url).search` verbatim, which
 * would let a client inject arbitrary params into the backend URL
 * (design.md Decision 7).
 *
 * @see design.md "Data Flow" (READ), "Decision 7"
 */
import { NextResponse } from "next/server";
import { adminBackendFetch } from "@/lib/admin/backend-fetch";

interface RouteContext {
  params: Promise<{ id: string; variantId: string }>;
}

const NO_STORE_HEADERS = { "Cache-Control": "private, no-store" } as const;
const ALLOWED_QUERY_PARAMS = ["limit", "before_id"] as const;

export async function GET(request: Request, { params }: RouteContext) {
  const { id, variantId } = await params;

  const incoming = new URL(request.url).searchParams;
  const outgoing = new URLSearchParams();
  for (const key of ALLOWED_QUERY_PARAMS) {
    const value = incoming.get(key);
    if (value !== null) {
      outgoing.set(key, value);
    }
  }
  const query = outgoing.toString();
  const path = `/admin/products/${id}/variants/${variantId}/stock/movements${
    query ? `?${query}` : ""
  }`;

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
