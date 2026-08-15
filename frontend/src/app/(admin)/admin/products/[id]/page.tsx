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
 * @see design.md "Data Flow"
 */
import { notFound } from "next/navigation";
import { headers } from "next/headers";
import { updateProductAction } from "../actions";
import { ImageManager, type AdminProductImage } from "../image-manager";
import { ProductForm, type ProductFormVariant } from "../product-form";
import { StockManager, type AdminVariantStock } from "../stock-manager";

interface AdminProduct {
  id: string;
  slug: string;
  name: string;
  model: string;
  variants: ProductFormVariant[];
}

interface EditProductPageProps {
  params: Promise<{ id: string }>;
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

export default async function EditProductPage({
  params,
}: EditProductPageProps) {
  const { id } = await params;
  const product = await fetchAdminProduct(id);

  if (!product) {
    notFound();
  }

  const images = await fetchAdminProductImages(product.id);
  const stock = await fetchAdminProductStock(product.id);
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
    </div>
  );
}
