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
 * Also fetches the first variant's stock movement history via the sibling
 * `app/api/admin/products/{id}/variants/{variantId}/stock/movements`
 * proxy (same pattern again) and renders `StockHistory` below
 * `StockManager` (admin-stock-movement-history). Multi-variant products
 * prefetch only `variants[0]`'s history server-side — switching variants
 * is a client-side fetch through the same proxy (design.md Open
 * Questions, consistent with proposal Q3's "one variant at a time").
 *
 * Reads `since`/`until` from `searchParams` (design.md DD2 — this page's
 * `searchParams` is the single source of truth for the history-view
 * date filter, mirroring `admin/stock/page.tsx`'s Decision 7
 * `searchParams`-is-a-Promise + array-collapse normalization) and
 * forwards them to the history proxy via a fresh `URLSearchParams` (the
 * encoding gotcha: a raw `+HH:MM` offset in a query string decodes to a
 * space if string-concatenated instead). An inverted range (`since`
 * later than `until`) is rejected HERE, before any history fetch is
 * issued — a page-level guard distinct from the backend's 422 for the
 * same condition (D10).
 *
 * @see design.md "Data Flow", "DD1", "DD2", "D13"
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

interface AdminProduct {
  id: string;
  slug: string;
  name: string;
  model: string;
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
 * `undefined`-preserving since `since`/`until` are optional wire values,
 * not empty-string form inputs).
 */
function normalizeDateParam(
  value: string | string[] | undefined,
): string | undefined {
  return Array.isArray(value) ? value[0] : value;
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
  const since = normalizeDateParam(resolvedSearchParams.since);
  const until = normalizeDateParam(resolvedSearchParams.until);
  const inverted = isInvertedRange(since, until);

  const product = await fetchAdminProduct(id);

  if (!product) {
    notFound();
  }

  const images = await fetchAdminProductImages(product.id);
  const stock = await fetchAdminProductStock(product.id);
  const firstVariantId = product.variants[0]?.id;
  // D10 / page-level guard (design.md DD1/DD2): an inverted range never
  // reaches the history fetch — no request is issued at all, distinct
  // from the backend's own 422 for the same condition.
  const stockHistory =
    firstVariantId && !inverted
      ? await fetchAdminProductStockHistory(
          product.id,
          firstVariantId,
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
      {firstVariantId && inverted && (
        <p role="alert" className="text-destructive text-sm">
          Start date is after end date.
        </p>
      )}
      {firstVariantId && !inverted && (
        <StockHistory
          productId={product.id}
          variantId={firstVariantId}
          initialHistory={stockHistory}
          since={since}
          until={until}
        />
      )}
    </div>
  );
}
