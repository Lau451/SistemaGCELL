/**
 * `/admin/stock` — catalog-wide, per-variant stock triage list. Server
 * Component fetching `app/api/admin/stock` (design.md's Data Flow: "fetch
 * same-origin"), the same cookie-forwarding pattern as `admin/products/page.tsx`
 * (see that file's header comment for why the cookie must be forwarded by
 * hand from a server-to-server RSC fetch).
 *
 * This is the first admin page reading `searchParams` for data fetching
 * (design.md Decision 7): Next 16 hands it as a Promise, and a repeated
 * query param arrives as an array — both are normalized here, not with
 * `Query`-style UI validation, before being forwarded to the proxy as
 * plain strings. The backend does the actual clamping/parsing.
 *
 * D13: each row links to `/admin/products/{product_id}` — triage-then-act.
 * D12: two distinct empty-state strings depending on whether a filter is
 * active, reusing the same normalization the backend applies so a blank
 * `?search=` never triggers the "no match" copy instead of "catalog empty".
 *
 * @see design.md "Data Flow", "Decision 6", "Decision 7"
 */
import Link from "next/link";
import { headers } from "next/headers";
import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

const LOW_STOCK_THRESHOLD = 5;

// Deterministic name → swatch-color mapping (decorative only, no data
// source for real hex values): common Spanish color names resolve to a
// real swatch, anything else falls back to a neutral dot so a row never
// renders an invalid CSS color.
const COLOR_SWATCHES: Record<string, string> = {
  negro: "#111111",
  blanco: "#f5f5f5",
  rojo: "#dc2626",
  azul: "#2563eb",
  verde: "#16a34a",
  gris: "#6b7280",
  dorado: "#ca8a04",
  plateado: "#9ca3af",
  rosa: "#ec4899",
  amarillo: "#eab308",
  morado: "#7c3aed",
  violeta: "#7c3aed",
  naranja: "#ea580c",
  celeste: "#38bdf8",
  marron: "#78350f",
};

function swatchColor(color: string): string {
  return COLOR_SWATCHES[color.trim().toLowerCase()] ?? "#d1c7cc";
}

interface AdminStockRow {
  product_id: string;
  product_slug: string;
  product_name: string;
  product_model: string;
  variant_id: string;
  color: string;
  quantity_on_hand: number;
}

interface AdminStockPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function collapseParam(value: string | string[] | undefined): string {
  const resolved = Array.isArray(value) ? value[0] : value;
  return resolved ?? "";
}

async function fetchAdminStock(
  below: string,
  search: string,
): Promise<AdminStockRow[] | null> {
  const headerList = await headers();
  const host = headerList.get("host");
  const protocol = headerList.get("x-forwarded-proto") ?? "http";
  const cookie = headerList.get("cookie") ?? "";

  const query = new URLSearchParams();
  if (below !== "") {
    query.set("below", below);
  }
  if (search !== "") {
    query.set("search", search);
  }
  const queryString = query.toString();

  const response = await fetch(
    `${protocol}://${host}/api/admin/stock${queryString ? `?${queryString}` : ""}`,
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

export default async function AdminStockPage({
  searchParams,
}: AdminStockPageProps) {
  const params = await searchParams;
  const below = collapseParam(params.below);
  const search = collapseParam(params.search);

  const rows = await fetchAdminStock(below, search);

  if (rows === null) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-10">
        <p role="alert" className="text-destructive text-sm">
          No pudimos cargar el stock.
        </p>
      </div>
    );
  }

  // Same normalization the backend applies (design.md Decision 6): a
  // blank/whitespace-only search or an unparseable below is "no filter".
  const filterActive = search.trim() !== "" || below.trim() !== "";
  const emptyStateCopy = filterActive
    ? "No hay variantes que coincidan con tu búsqueda o filtro."
    : "Todavía no hay variantes en el catálogo.";

  // Decorative triage counts only (Phase 3 mockup's low-stock banner) —
  // derived from the already-fetched `rows`, no additional request.
  const zeroCount = rows.filter((row) => row.quantity_on_hand === 0).length;
  const lowCount = rows.filter(
    (row) =>
      row.quantity_on_hand > 0 && row.quantity_on_hand <= LOW_STOCK_THRESHOLD,
  ).length;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 px-4 py-10">
      <div className="flex items-center justify-between">
        <h1 className="font-heading text-2xl font-semibold">Stock</h1>
      </div>

      {(zeroCount > 0 || lowCount > 0) && (
        <div className="border-warning/30 bg-warning/10 text-warning flex items-center gap-2 rounded-lg border px-4 py-3 text-sm">
          <AlertTriangle className="size-4 shrink-0" />
          <span>
            {lowCount > 0 && `${lowCount} variante${lowCount === 1 ? "" : "s"} con stock bajo`}
            {lowCount > 0 && zeroCount > 0 && " · "}
            {zeroCount > 0 && `${zeroCount} sin stock`}
          </span>
        </div>
      )}

      <form method="get" className="flex flex-wrap items-end gap-3">
        <Input
          type="text"
          name="search"
          defaultValue={search}
          placeholder="Buscar nombre de producto o color"
          label="Buscar"
          className="w-64"
        />
        <Input
          type="number"
          name="below"
          defaultValue={below}
          placeholder="Menor a"
          label="Menor a"
          className="w-24"
        />
        <Button type="submit" variant="secondary">
          Filtrar
        </Button>
      </form>

      {rows.length === 0 ? (
        <p className="text-muted-foreground text-sm">{emptyStateCopy}</p>
      ) : (
        <Card className="gap-0 overflow-hidden py-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-border bg-muted/40 text-muted-foreground border-b text-xs font-medium tracking-wide uppercase">
                  <th className="px-5 py-3">Producto</th>
                  <th className="px-5 py-3">Modelo</th>
                  <th className="px-5 py-3">Color</th>
                  <th className="px-5 py-3">Cantidad</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const isZero = row.quantity_on_hand === 0;
                  const isLow =
                    !isZero && row.quantity_on_hand <= LOW_STOCK_THRESHOLD;
                  return (
                    <tr
                      key={row.variant_id}
                      className="border-border border-b align-top last:border-b-0"
                    >
                      <td className="px-5 py-3">
                        <Link
                          href={`/admin/products/${row.product_id}`}
                          className={
                            isZero
                              ? "text-destructive font-medium underline underline-offset-2"
                              : "font-medium underline underline-offset-2"
                          }
                        >
                          {row.product_name}
                        </Link>
                      </td>
                      <td className="text-muted-foreground px-5 py-3">
                        {row.product_model}
                      </td>
                      <td className="px-5 py-3">
                        <span className="inline-flex items-center gap-2">
                          <span
                            aria-hidden="true"
                            className="border-border size-3 shrink-0 rounded-full border"
                            style={{ backgroundColor: swatchColor(row.color) }}
                          />
                          {row.color}
                        </span>
                      </td>
                      <td
                        className={
                          isZero
                            ? "text-destructive px-5 py-3"
                            : "px-5 py-3"
                        }
                      >
                        <span className="inline-flex items-center gap-2">
                          <span>{row.quantity_on_hand}</span>
                          {isZero && <Badge variant="danger">Sin stock</Badge>}
                          {isLow && <Badge variant="warning">Stock bajo</Badge>}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
