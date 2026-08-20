/**
 * `/admin/products/[id]` — edit page. Server Component fetching
 * `app/api/admin/products/{id}` (design.md's Data Flow: "fetch
 * same-origin"), same cookie-forwarding pattern as `products/page.tsx`:
 * a server-to-server request from an RSC does NOT automatically carry
 * the visiting browser's cookies, so the incoming request's `cookie`
 * header is forwarded by hand.
 *
 * Renders `product-form.tsx` wired to `updateProductAction`, bound to
 * this product's id via `.bind` (a Server Action may take leading
 * bound arguments ahead of the `useActionState`-supplied `prevState`/
 * `formData` pair). No slug field exposed anywhere — the persisted slug
 * never changes after creation (spec: "Slug never changes after
 * creation, even on rename").
 *
 * Also fetches this product's images via the sibling
 * `app/api/admin/products/{id}/images` proxy (same self-referential,
 * cookie-forwarded fetch pattern as `fetchAdminProduct`) and renders
 * `ImageManager` below the form — the only surface for the upload/
 * delete/reorder Server Actions (Phase 7).
 *
 * Also fetches this product's current per-variant stock via the sibling
 * `app/api/admin/products/{id}/stock` proxy (same pattern again) and
 * renders `StockManager` below the images — the only surface for
 * `recordStockMovementAction` (Phase B / admin-stock-management).
 *
 * Also fetches the active variant's stock movement history via the
 * sibling `app/api/admin/products/{id}/variants/{variantId}/stock/movements`
 * proxy (same pattern again) and renders `StockHistory` below
 * `StockManager` (admin-stock-movement-history), plus a `VariantSwitcher`
 * (design.md D14/DD3) that scopes ONLY that history section. The active
 * variant is resolved from `?variant=<id>` (DD4) via `resolveActiveVariant`
 * — an in-memory membership check against the already-authorized
 * `product.variants`, the same "never distinguish missing vs. foreign"
 * idiom as `list_variant_stock_movements.py`'s `VariantNotFoundError`
 * guard. Absent `?variant=` defaults to `variants[0]` (backward
 * compatible with every pre-switcher URL). An unknown, foreign, or
 * malformed `?variant=` value calls `notFound()` (404, never a silent
 * fallback and never 403) BEFORE any movement-history fetch is issued —
 * variant switching is a real server-rendered navigation, never a
 * client-side fetch. `StockManager`'s own write-target `<select>` stays
 * entirely independent of `?variant=` (D16) — it is not touched here.
 *
 * Reads `since`/`until` from the same `searchParams` (design.md DD2 —
 * this page's `searchParams` is the single source of truth for the
 * history-view date filter, mirroring `admin/stock/page.tsx`'s Decision 7
 * `searchParams`-is-a-Promise + array-collapse normalization) and
 * forwards them to the history proxy via a fresh `URLSearchParams` (the
 * encoding gotcha: a raw `+HH:MM` offset in a query string decodes to a
 * space if string-concatenated instead). An inverted range (`since`
 * later than `until`) is rejected HERE, before any history fetch is
 * issued — a page-level guard distinct from the backend's 422 for the
 * same condition (D10). Every `VariantSwitcher` link carries the active
 * `since`/`until` forward (D12), so switching variants never silently
 * clears an applied filter.
 *
 * @see design.md "Data Flow", "DD1", "DD2", "DD3", "DD4", "D12", "D13"
 */
import { notFound } from "next/navigation";
import { headers } from "next/headers";
import { updateProductAction } from "../actions";
import { ImageManager, type AdminProductImage } from "../image-manager";
import { ProductForm, type ProductFormVariant } from "../product-form";
import { StockManager, type AdminVariantStock } from "../stock-manager";
import {
  StockHistory,
  type AdminStockMovementPage,
} from "../stock-history";
import { isInvertedRange } from "../stock-history-dates";
import { VariantSwitcher } from "../variant-switcher";

interface AdminProduct {
  id: string;
  slug: string;
  name: string;
  model: string;
  description: string | null;
  short_description: string | null;
  variants: ProductFormVariant[];
}

interface EditProductPageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * `searchParams` values are `string | string[] | undefined` (a repeated
 * key yields an array) — take the first entry, then treat a blank/absent
 * value as "no filter" (design.md DD4's "Shared param normalization",
 * same rule `admin/stock/page.tsx`'s `collapseParam` applies, but
 * `undefined`-preserving since `since`/`until`/`variant` are optional
 * wire values, not empty-string form inputs). Shared by the date-filter
 * params AND `?variant=` — DD4 calls out this is the same normalization
 * rule for all three.
 */
function normalizeParam(
  value: string | string[] | undefined,
): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

/**
 * DD4's membership guard: matches the normalized `?variant=` value
 * against `product.variants` — data already fetched under the
 * authenticated proxy, so this is a pure in-memory check, no extra
 * backend read. Returns `null` for an unknown, foreign, or malformed
 * value (all three are indistinguishable on purpose — the same "never
 * leak existence" idiom as `VariantNotFoundError` in
 * `list_variant_stock_movements.py`), which the caller turns into
 * `notFound()`. An absent value defaults to `variants[0]`, keeping every
 * pre-switcher URL working.
 */
function resolveActiveVariant(
  variants: ProductFormVariant[],
  raw: string | string[] | undefined,
): ProductFormVariant | null {
  const normalized = normalizeParam(raw);
  if (normalized === undefined || normalized === "") {
    return variants[0] ?? null;
  }
  return variants.find((variant) => variant.id === normalized) ?? null;
}

async function fetchAdminProduct(id: string): Promise<AdminProduct | null> {
  const headerList = await headers();
  const host = headerList.get("host");
  const protocol = headerList.get("x-forwarded-proto") ?? "http";
  const cookie = headerList.get("cookie") ?? "";

  const response = await fetch(
    `${protocol}://${host}/api/admin/products/${id}`,
    {
      headers: { cookie },
      cache: "no-store",
    },
  );

  if (!response.ok) {
    return null;
  }

  return response.json();
}

async function fetchAdminProductImages(
  id: string,
): Promise<AdminProductImage[]> {
  const headerList = await headers();
  const host = headerList.get("host");
  const protocol = headerList.get("x-forwarded-proto") ?? "http";
  const cookie = headerList.get("cookie") ?? "";

  const response = await fetch(
    `${protocol}://${host}/api/admin/products/${id}/images`,
    {
      headers: { cookie },
      cache: "no-store",
    },
  );

  if (!response.ok) {
    return [];
  }

  return response.json();
}

async function fetchAdminProductStock(
  id: string,
): Promise<AdminVariantStock[]> {
  const headerList = await headers();
  const host = headerList.get("host");
  const protocol = headerList.get("x-forwarded-proto") ?? "http";
  const cookie = headerList.get("cookie") ?? "";

  const response = await fetch(
    `${protocol}://${host}/api/admin/products/${id}/stock`,
    {
      headers: { cookie },
      cache: "no-store",
    },
  );

  if (!response.ok) {
    return [];
  }

  return response.json();
}

const EMPTY_STOCK_HISTORY: AdminStockMovementPage = {
  items: [],
  next_before_id: null,
};

async function fetchAdminProductStockHistory(
  id: string,
  variantId: string,
  since: string | undefined,
  until: string | undefined,
): Promise<AdminStockMovementPage> {
  const headerList = await headers();
  const host = headerList.get("host");
  const protocol = headerList.get("x-forwarded-proto") ?? "http";
  const cookie = headerList.get("cookie") ?? "";

  // Fresh `URLSearchParams` rebuild, never string concatenation — see this
  // file's header docstring on the `+HH:MM`-decodes-to-a-space gotcha.
  const query = new URLSearchParams();
  if (since) {
    query.set("since", since);
  }
  if (until) {
    query.set("until", until);
  }
  const queryString = query.toString();

  const response = await fetch(
    `${protocol}://${host}/api/admin/products/${id}/variants/${variantId}/stock/movements${
      queryString ? `?${queryString}` : ""
    }`,
    {
      headers: { cookie },
      cache: "no-store",
    },
  );

  if (!response.ok) {
    return EMPTY_STOCK_HISTORY;
  }

  return response.json();
}

export default async function EditProductPage({
  params,
  searchParams,
}: EditProductPageProps) {
  const { id } = await params;
  const resolvedSearchParams = await searchParams;
  const since = normalizeParam(resolvedSearchParams.since);
  const until = normalizeParam(resolvedSearchParams.until);
  const inverted = isInvertedRange(since, until);

  const product = await fetchAdminProduct(id);

  if (!product) {
    notFound();
  }

  // DD4: membership-checked BEFORE any history fetch, mirroring
  // "ownership checked before any read". Unknown/foreign/malformed →
  // 404, never a fallback to `variants[0]` and never 403. A product with
  // ZERO variants is a distinct, pre-existing, still-locked case
  // (admin-product-management: "A Product May Have Zero Active Variants
  // Without Being Retired" — the edit page MUST stay reachable) — DD4's
  // guard only applies once the product actually HAS at least one
  // variant to resolve against.
  const hasVariants = product.variants.length > 0;
  const activeVariant = hasVariants
    ? resolveActiveVariant(product.variants, resolvedSearchParams.variant)
    : null;
  if (hasVariants && !activeVariant) {
    notFound();
  }

  const images = await fetchAdminProductImages(product.id);
  const stock = await fetchAdminProductStock(product.id);
  // D10 / page-level guard (design.md DD1/DD2): an inverted range never
  // reaches the history fetch — no request is issued at all, distinct
  // from the backend's own 422 for the same condition.
  const stockHistory =
    activeVariant && !inverted
      ? await fetchAdminProductStockHistory(
          product.id,
          activeVariant.id,
          since,
          until,
        )
      : EMPTY_STOCK_HISTORY;
  const updateAction = updateProductAction.bind(null, product.id);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-10">
      <h1 className="text-2xl font-semibold">Edit product</h1>
      <ProductForm
        productId={product.id}
        initialName={product.name}
        initialModel={product.model}
        initialDescription={product.description ?? ""}
        initialShortDescription={product.short_description ?? ""}
        initialVariants={product.variants}
        action={updateAction}
        submitLabel="Save changes"
      />
      <ImageManager
        productId={product.id}
        variants={product.variants}
        initialImages={images}
      />
      <StockManager productId={product.id} initialStock={stock} />
      {activeVariant && (
        <VariantSwitcher
          productId={product.id}
          variants={product.variants}
          activeVariantId={activeVariant.id}
          since={since}
          until={until}
        />
      )}
      {activeVariant && inverted && (
        <p role="alert" className="text-destructive text-sm">
          Start date is after end date.
        </p>
      )}
      {activeVariant && !inverted && (
        <StockHistory
          productId={product.id}
          variantId={activeVariant.id}
          initialHistory={stockHistory}
          since={since}
          until={until}
        />
      )}
    </div>
  );
}
