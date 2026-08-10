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

export type CatalogEmptyStateVariant = "empty-catalog" | "no-results" | "error";

export interface CatalogEmptyStateProps {
  variant: CatalogEmptyStateVariant;
}

const COPY: Record<
  CatalogEmptyStateVariant,
  { testId: string; heading: string; body: string }
> = {
  "empty-catalog": {
    testId: "catalog-empty-state-empty-catalog",
    heading: "Estamos preparando el catálogo",
    body: "Todavía no hay productos publicados. Volvé a visitarnos pronto.",
  },
  "no-results": {
    testId: "catalog-empty-state-no-results",
    heading: "No encontramos productos para tu búsqueda",
    body: "Probá con otros términos o quitá algunos filtros.",
  },
  error: {
    testId: "catalog-empty-state-error",
    heading: "No pudimos cargar el catálogo",
    body: "Ocurrió un problema al conectar con el catálogo. Intentá de nuevo en unos minutos.",
  },
};

export function CatalogEmptyState({ variant }: CatalogEmptyStateProps) {
  const copy = COPY[variant];

  return (
    <div
      role="status"
      data-testid={copy.testId}
      className="flex flex-col items-center gap-2 px-4 py-16 text-center"
    >
      <h2 className="text-lg font-semibold">{copy.heading}</h2>
      <p className="text-muted-foreground max-w-md text-sm">{copy.body}</p>
      {variant === "no-results" && (
        <Link
          href="/catalog"
          className="text-primary mt-2 text-sm underline-offset-4 hover:underline"
        >
          Limpiar filtros
        </Link>
      )}
      {variant === "error" && (
        <Link
          href="/"
          className="text-primary mt-2 text-sm underline-offset-4 hover:underline"
        >
          Reintentar
        </Link>
      )}
    </div>
  );
}
