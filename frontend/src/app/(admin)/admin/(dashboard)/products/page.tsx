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
import { ImageOff, Pencil, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { IconButton } from "@/components/ui/icon-button";
import { retireProductAction } from "./actions";

interface AdminProductVariant {
  id: string;
  color: string;
  price: string;
  cost: string;
  quantity_on_hand: number;
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
        <p role="alert" className="text-destructive text-sm">
          No pudimos cargar los productos.
        </p>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-10">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-2xl font-semibold">Productos</h1>
        <Link
          href="/admin/products/new"
          className="text-brand-primary text-sm font-medium underline underline-offset-2"
        >
          Nuevo producto
        </Link>
      </div>
      <Card className="gap-0 overflow-hidden py-0">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-border bg-muted/40 text-muted-foreground border-b text-xs font-medium tracking-wide uppercase">
                <th className="px-5 py-3">Producto</th>
                <th className="px-5 py-3">Variantes</th>
                <th className="px-5 py-3">Estado</th>
                <th className="px-5 py-3">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {products.map((product) => (
                <tr
                  key={product.id}
                  className="border-border border-b align-top last:border-b-0"
                >
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <div className="bg-muted flex size-10 shrink-0 items-center justify-center rounded-lg">
                        <ImageOff className="text-muted-foreground size-4" />
                      </div>
                      <div className="flex flex-col">
                        <span className="font-medium">{product.name}</span>
                        <span className="text-muted-foreground text-xs">
                          {product.model}
                        </span>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    {product.variants.length === 0 ? (
                      <span className="text-muted-foreground">Sin variantes</span>
                    ) : (
                      <ul className="flex flex-col gap-1">
                        {product.variants.map((variant) => {
                          const isZero = variant.quantity_on_hand === 0;
                          return (
                            <li
                              key={variant.id}
                              className={isZero ? "text-destructive" : undefined}
                            >
                              {variant.color} — {variant.price} / {variant.cost} —{" "}
                              <span>{variant.quantity_on_hand}</span>
                              {isZero && (
                                <Badge variant="danger" className="ml-1.5 align-middle">
                                  Sin stock
                                </Badge>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    )}
                  </td>
                  <td className="px-5 py-4">
                    <Badge variant="success">Activo</Badge>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-2">
                      <IconButton
                        variant="outline"
                        size="sm"
                        aria-label="Editar producto"
                        render={<Link href={`/admin/products/${product.id}`} />}
                      >
                        <Pencil />
                      </IconButton>
                      <form action={retireProductAction}>
                        <input
                          type="hidden"
                          name="product-id"
                          value={product.id}
                        />
                        <IconButton
                          type="submit"
                          variant="outline"
                          size="sm"
                          aria-label="Retirar producto"
                          className="border-destructive/40 text-destructive hover:bg-destructive/10"
                        >
                          <Trash2 />
                        </IconButton>
                      </form>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
