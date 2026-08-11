/**
 * `GET /api/admin/products/[id]` — single-product proxy Route Handler,
 * used by the edit page (`[id]/page.tsx`) to fetch the product it needs
 * to prefill `product-form.tsx`. Relays directly to the backend's
 * `GET /admin/products/{id}` (added post-PR3 to close a design.md gap
 * that had been worked around with a list-and-filter relay — see git
 * history for that superseded version). Same auth-gate-then-relay
 * pattern as the list route in `../route.ts`. Next 16 dynamic routes
 * take `params: Promise<{ id: string }>`.
 *
 * @see design.md "Frontend relay"
 */
import { NextResponse } from "next/server";
import { adminBackendFetch } from "@/lib/admin/backend-fetch";

interface RouteContext {
  params: Promise<{ id: string }>;
}

const NO_STORE_HEADERS = { "Cache-Control": "private, no-store" } as const;

export async function GET(_request: Request, { params }: RouteContext) {
  const { id } = await params;
  const result = await adminBackendFetch(`/admin/products/${id}`);

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
