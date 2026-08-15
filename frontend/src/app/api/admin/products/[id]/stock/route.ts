/**
 * `GET /api/admin/products/[id]/stock` — proxy Route Handler used by the
 * product detail page (`[id]/page.tsx`) to fetch the initial per-variant
 * stock levels for `stock-manager.tsx`. Relays directly to the backend's
 * `GET /admin/products/{id}/stock`, mirroring the EXACT
 * auth-gate-then-relay pattern already used by the sibling
 * `images/route.ts` proxy.
 *
 * @see design.md "Data Flow" (READ)
 */
import { NextResponse } from "next/server";
import { adminBackendFetch } from "@/lib/admin/backend-fetch";

interface RouteContext {
  params: Promise<{ id: string }>;
}

const NO_STORE_HEADERS = { "Cache-Control": "private, no-store" } as const;

export async function GET(_request: Request, { params }: RouteContext) {
  const { id } = await params;
  const result = await adminBackendFetch(`/admin/products/${id}/stock`);

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
