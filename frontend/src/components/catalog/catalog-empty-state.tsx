/**
 * The three deliberate "nothing to show" states for the catalog listing —
 * `empty-catalog` (zero products exist at all), `no-results` (a search or
 * filter matched nothing), and `error` (the catalog read failed). Each
 * renders a distinct `role="status"` + `data-testid` so RTL can assert they
 * are genuinely different states, per spec's "Deliberate Empty and
 * No-Results States" requirement.
 *
 * @see design.md "Empty / No-Results / Error States"
 */

import Link from "next/link";
import { AlertTriangle, PackageSearch, SearchX, type LucideIcon } from "lucide-react";

export type CatalogEmptyStateVariant = "empty-catalog" | "no-results" | "error";

export interface CatalogEmptyStateProps {
  variant: CatalogEmptyStateVariant;
}

const COPY: Record<
  CatalogEmptyStateVariant,
  { testId: string; heading: string; body: string; icon: LucideIcon }
> = {
  "empty-catalog": {
    testId: "catalog-empty-state-empty-catalog",
    heading: "Estamos preparando el catálogo",
    body: "Todavía no hay productos publicados. Volvé a visitarnos pronto.",
    icon: PackageSearch,
  },
  "no-results": {
    testId: "catalog-empty-state-no-results",
    heading: "No encontramos productos para tu búsqueda",
    body: "Probá con otros términos o quitá algunos filtros.",
    icon: SearchX,
  },
  error: {
    testId: "catalog-empty-state-error",
    heading: "No pudimos cargar el catálogo",
    body: "Ocurrió un problema al conectar con el catálogo. Intentá de nuevo en unos minutos.",
    icon: AlertTriangle,
  },
};

export function CatalogEmptyState({ variant }: CatalogEmptyStateProps) {
  const copy = COPY[variant];
  const Icon = copy.icon;

  return (
    <div
      role="status"
      data-testid={copy.testId}
      className="mx-auto flex max-w-md flex-col items-center gap-3 px-4 py-20 text-center"
    >
      <span className="flex size-14 items-center justify-center rounded-full bg-brand-blush text-brand-primary">
        <Icon aria-hidden="true" className="size-7" />
      </span>
      <h2 className="font-heading text-lg font-semibold text-foreground">
        {copy.heading}
      </h2>
      <p className="text-muted-foreground text-sm">{copy.body}</p>
      {variant === "no-results" && (
        <Link
          href="/catalog"
          className="mt-2 text-sm font-medium text-brand-primary underline-offset-4 hover:underline"
        >
          Limpiar filtros
        </Link>
      )}
      {variant === "error" && (
        <Link
          href="/"
          className="mt-2 text-sm font-medium text-brand-primary underline-offset-4 hover:underline"
        >
          Reintentar
        </Link>
      )}
    </div>
  );
}
