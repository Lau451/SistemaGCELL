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
        <p role="alert">Unable to load stock.</p>
      </div>
    );
  }

  // Same normalization the backend applies (design.md Decision 6): a
  // blank/whitespace-only search or an unparseable below is "no filter".
  const filterActive = search.trim() !== "" || below.trim() !== "";
  const emptyStateCopy = filterActive
    ? "No variants match your search or filter."
    : "No variants in the catalog yet.";

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Stock</h1>
      </div>
      <form method="get" className="flex items-center gap-3">
        <input
          type="text"
          name="search"
          defaultValue={search}
          placeholder="Search product name or color"
          className="border-border rounded border px-3 py-1.5 text-sm"
        />
        <input
          type="number"
          name="below"
          defaultValue={below}
          placeholder="Below"
          className="border-border w-24 rounded border px-3 py-1.5 text-sm"
        />
        <button
          type="submit"
          className="text-sm font-medium underline"
        >
          Filter
        </button>
      </form>
      {rows.length === 0 ? (
        <p>{emptyStateCopy}</p>
      ) : (
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-border border-b">
              <th className="py-2">Product</th>
              <th className="py-2">Model</th>
              <th className="py-2">Color</th>
              <th className="py-2">Quantity</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const isZero = row.quantity_on_hand === 0;
              return (
                <tr
                  key={row.variant_id}
                  className="border-border border-b align-top"
                >
                  <td className="py-2">
                    <Link
                      href={`/admin/products/${row.product_id}`}
                      className={
                        isZero
                          ? "text-destructive font-medium underline"
                          : "font-medium underline"
                      }
                    >
                      {row.product_name}
                    </Link>
                  </td>
                  <td className="py-2">{row.product_model}</td>
                  <td className="py-2">{row.color}</td>
                  <td className={isZero ? "text-destructive py-2" : "py-2"}>
                    <span>{row.quantity_on_hand}</span>
                    {isZero && (
                      <span className="ml-1 text-xs font-medium">
                        Out of stock
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
