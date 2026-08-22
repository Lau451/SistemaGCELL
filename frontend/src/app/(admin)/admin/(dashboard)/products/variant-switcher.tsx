/**
 * `VariantSwitcher` — server-rendered link row on the product stock page
 * (`[id]/stock/page.tsx`), letting the admin choose which variant's stock
 * movement history is displayed (design.md D14/DD3). Deliberately a
 * `<nav>` of `<Link>`s, not a `<select>` + `router.push`: this is
 * navigation, not a form control, and a server component needs no
 * client-side island to express it.
 *
 * Scopes exactly one section (`StockHistory`) — `StockManager`'s
 * independent write-target `<select>` is untouched (D16, DD3 "Scope of
 * the switcher").
 *
 * Renders `null` (no control, no wrapper markup) when the product has
 * fewer than two variants, so a single-variant product's page stays
 * byte-identical to before the switcher existed. The active variant's
 * link carries `aria-current="page"` — a semantic proxy for tests,
 * matching the repo's existing "Out of stock" label precedent rather
 * than asserting CSS classes.
 *
 * Every `href` is built with `URLSearchParams`, never string
 * concatenation (the same `+HH:MM`-decodes-to-a-space encoding gotcha
 * `stock-history-dates.ts` documents), carrying `variant` plus any
 * active `since`/`until` so switching variants preserves the active date
 * filter by construction (D12).
 *
 * @see design.md "DD3", "DD4", "Interfaces / Contracts"
 */
import Link from "next/link";
import { cn } from "@/lib/utils";

export interface VariantSwitcherProps {
  productId: string;
  variants: { id: string; color: string }[];
  activeVariantId: string;
  since?: string;
  until?: string;
}

function buildVariantHref(
  productId: string,
  variantId: string,
  since: string | undefined,
  until: string | undefined,
): string {
  const query = new URLSearchParams();
  query.set("variant", variantId);
  if (since) {
    query.set("since", since);
  }
  if (until) {
    query.set("until", until);
  }
  return `/admin/products/${productId}/stock?${query.toString()}`;
}

export function VariantSwitcher({
  productId,
  variants,
  activeVariantId,
  since,
  until,
}: VariantSwitcherProps) {
  if (variants.length < 2) {
    return null;
  }

  return (
    <nav aria-label="Selector de variante" className="flex flex-wrap gap-2">
      {variants.map((variant) => {
        const isActive = variant.id === activeVariantId;
        return (
          <Link
            key={variant.id}
            href={buildVariantHref(productId, variant.id, since, until)}
            aria-current={isActive ? "page" : undefined}
            className={cn(
              "rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors",
              isActive
                ? "border-brand-primary bg-brand-blush text-brand-primary"
                : "border-border text-muted-foreground hover:bg-muted",
            )}
          >
            {variant.color}
          </Link>
        );
      })}
    </nav>
  );
}
