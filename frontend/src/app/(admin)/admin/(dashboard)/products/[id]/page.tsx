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
 * Stock management (record-movement form, history, variant switcher)
 * lives at the sibling `/admin/products/[id]/stock` route, not here —
 * this page is product-info-only (name/model/description/images) so an
 * admin arriving from "Productos" never sees stock controls, and an
 * admin arriving from "Stock" never sees the product-info form. A link
 * near the heading crosses over to the stock page.
 *
 * @see design.md "Data Flow", "DD1"
 */
import Link from "next/link";
import { notFound } from "next/navigation";
import { headers } from "next/headers";
import { updateProductAction } from "../actions";
import { ImageManager, type AdminProductImage } from "../image-manager";
import { ProductForm, type ProductFormVariant } from "../product-form";

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

export default async function EditProductPage({
  params,
}: EditProductPageProps) {
  const { id } = await params;

  const product = await fetchAdminProduct(id);

  if (!product) {
    notFound();
  }

  const images = await fetchAdminProductImages(product.id);
  const updateAction = updateProductAction.bind(null, product.id);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 px-4 py-10">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-2xl font-semibold">
          Editar producto
        </h1>
        <Link
          href={`/admin/products/${product.id}/stock`}
          className="text-brand-primary text-sm font-medium underline underline-offset-2"
        >
          Ver stock →
        </Link>
      </div>
      <ProductForm
        productId={product.id}
        initialName={product.name}
        initialModel={product.model}
        initialDescription={product.description ?? ""}
        initialShortDescription={product.short_description ?? ""}
        initialVariants={product.variants}
        action={updateAction}
        submitLabel="Guardar cambios"
      />
      <ImageManager
        productId={product.id}
        variants={product.variants}
        initialImages={images}
      />
    </div>
  );
}
