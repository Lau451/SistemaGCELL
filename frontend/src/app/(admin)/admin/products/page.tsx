/**
 * `/admin/products` — the ONE read-only proof page this change ships
 * (`product_decisions.scope` in `state.yaml`: minimal scope, no create/
 * edit/delete UI). Server Component fetching `app/api/admin/products`
 * (design.md's Data Flow: "fetch same-origin").
 *
 * This is a server-to-server request from an RSC, not a browser fetch —
 * a plain `fetch()` from server code does NOT automatically carry the
 * visiting browser's cookies, so the incoming request's `cookie` header
 * (read via `next/headers`) is forwarded by hand. Without this, the
 * proxy route's `createSessionClient()` would see no session on every
 * request and this page would always render the error state, even for
 * a genuinely logged-in admin.
 *
 * @see design.md "Data Flow", "`GET /api/admin/products`"
 */
import { headers } from "next/headers";

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
      <h1 className="text-2xl font-semibold">Products</h1>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-border border-b">
            <th className="py-2">Name</th>
            <th className="py-2">Model</th>
            <th className="py-2">Color</th>
            <th className="py-2">Price</th>
            <th className="py-2">Cost</th>
          </tr>
        </thead>
        <tbody>
          {products.flatMap((product) =>
            product.variants.map((variant) => (
              <tr key={variant.id} className="border-border border-b">
                <td className="py-2">{product.name}</td>
                <td className="py-2">{product.model}</td>
                <td className="py-2">{variant.color}</td>
                <td className="py-2">{variant.price}</td>
                <td className="py-2">{variant.cost}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </div>
  );
}
