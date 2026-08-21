/**
 * `StockAlertBadge` — async Server Component mounted inside the "Stock"
 * nav link in `admin/layout.tsx` (behind `<Suspense fallback={null}>` so
 * the shell renders immediately, design.md Decision 1). Fetches the
 * existing `GET /api/admin/stock?below=5` route with the exact
 * cookie-forwarding idiom `stock/page.tsx` already uses, and derives the
 * low-stock count as `rows.length` — the route's `?below=5` already
 * narrows server-side, so no client-side filtering is needed (D5).
 *
 * Never throws (design.md Decision 2): there is no `error.tsx` under the
 * `(admin)/` route group, so an uncaught exception here would crash the
 * whole admin shell, not just this badge. A network error, a non-ok
 * response (e.g. an unauthenticated `401`), and a malformed body all
 * collapse to `null` — the same render as a genuine zero count (D6).
 *
 * @see design.md "Decision 1", "Decision 2", "Interfaces / Contracts"
 */
import { headers } from "next/headers";
import { Badge } from "@/components/ui/badge";

async function fetchLowStockCount(): Promise<number | null> {
  try {
    const headerList = await headers();
    const host = headerList.get("host");
    const protocol = headerList.get("x-forwarded-proto") ?? "http";
    const cookie = headerList.get("cookie") ?? "";

    const response = await fetch(
      `${protocol}://${host}/api/admin/stock?below=5`,
      {
        headers: { cookie },
        cache: "no-store",
      },
    );

    if (!response.ok) {
      return null;
    }

    const rows = await response.json();
    return Array.isArray(rows) ? rows.length : null;
  } catch {
    return null;
  }
}

export async function StockAlertBadge() {
  const count = await fetchLowStockCount();

  if (count === null || count === 0) {
    return null;
  }

  return (
    <Badge variant="danger" className="ml-1 border-white/20 bg-white/10">
      ({count})
    </Badge>
  );
}
