/**
 * `/admin/products` — the admin product list. Server Component fetching
 * `app/api/admin/products` (design.md's Data Flow: "fetch same-origin").
 *
 * This is a server-to-server request from an RSC, not a browser fetch —
 * a plain `fetch()` from server code does NOT automatically carry the
 * visiting browser's cookies, so the incoming request's `cookie` header
 * (read via `next/headers`) is forwarded by hand. Without this, the
 * proxy route's `createSessionClient()` would see no session on every
 * request and this page would always render the error state, even for
 * a genuinely logged-in admin.
 *
 * One row per PRODUCT, not per variant (PR4 change): a product with zero
 * active variants MUST still appear in this list, editable (spec: "A
 * Product May Have Zero Active Variants Without Being Retired") — a
 * per-variant `flatMap` renders zero rows for an empty `variants` array,
 * making such a product invisible here.
 *
 * @see design.md "Data Flow", "`GET /api/admin/products`"
 */
import Link from "next/link";
import { headers } from "next/headers";
import { Button } from "@/components/ui/button";
import { retireProductAction } from "./actions";

interface AdminProductVariant {
  id: string;
  color: string;
  price: string;
  cost: string;
}

interface AdminProduct {
  id: string;
  slug: string;
  name: string;
  model: string;
  variants: AdminProductVariant[];
}

async function fetchAdminProducts(): Promise<AdminProduct[] | null> {
  const headerList = await headers();
  const host = headerList.get("host");
  const protocol = headerList.get("x-forwarded-proto") ?? "http";
  const cookie = headerList.get("cookie") ?? "";

  const response = await fetch(`${protocol}://${host}/api/admin/products`, {
    headers: { cookie },
    cache: "no-store",
  });

  if (!response.ok) {
    return null;
  }

  return response.json();
}

export default async function AdminProductsPage() {
  const products = await fetchAdminProducts();

  if (products === null) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10">
        <p role="alert">Unable to load products.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Products</h1>
        <Link
          href="/admin/products/new"
          className="text-sm font-medium underline"
        >
          New product
        </Link>
      </div>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-border border-b">
            <th className="py-2">Name</th>
            <th className="py-2">Model</th>
            <th className="py-2">Variants</th>
            <th className="py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {products.map((product) => (
            <tr key={product.id} className="border-border border-b align-top">
              <td className="py-2">{product.name}</td>
              <td className="py-2">{product.model}</td>
              <td className="py-2">
                {product.variants.length === 0 ? (
                  <span className="text-muted-foreground">No variants</span>
                ) : (
                  <ul className="flex flex-col gap-1">
                    {product.variants.map((variant) => (
                      <li key={variant.id}>
                        {variant.color} — {variant.price} / {variant.cost}
                      </li>
                    ))}
                  </ul>
                )}
              </td>
              <td className="py-2">
                <div className="flex items-center gap-3">
                  <Link
                    href={`/admin/products/${product.id}`}
                    className="text-sm font-medium underline"
                  >
                    Edit
                  </Link>
                  <form action={retireProductAction}>
                    <input type="hidden" name="product-id" value={product.id} />
                    <Button type="submit" variant="destructive" size="sm">
                      Retire
                    </Button>
                  </form>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
