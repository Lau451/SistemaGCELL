/**
 * `GET /api/admin/products/[id]/images` — proxy Route Handler used by the
 * product detail page (`[id]/page.tsx`) to fetch the initial image list
 * for `image-manager.tsx`. Relays directly to the backend's
 * `GET /admin/products/{id}/images`, mirroring the EXACT
 * auth-gate-then-relay pattern already used by the sibling
 * `[id]/route.ts` single-product proxy. This route is not listed in
 * design.md's File Changes table — it closes the same gap `[id]/route.ts`
 * closed for the product fetch itself (see that file's own comment), now
 * needed so a Server Component can fetch this product's images the same
 * self-referential way it already fetches the product.
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
  const result = await adminBackendFetch(`/admin/products/${id}/images`);

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
