"use client";

/**
 * Client-side search/model/color/pagination controls for the catalog
 * listing. Receives the server-rendered first page as initial props (so
 * the initial ISR render stays untouched — `revalidate = 300` on the
 * `page.tsx` shells is unaffected) and, on any filter change, fetches
 * `/api/catalog` and replaces the rendered cards in local state —
 * `history.replaceState` keeps deep-linkable URLs without a full
 * navigation/reload.
 *
 * @see design.md "Data Flow" (Filter/search change branch),
 * "Route Handler Contract — GET /api/catalog"
 */
import { useCallback, useState, type FormEvent } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Chip } from "@/components/ui/chip";
import { Input } from "@/components/ui/input";
import { CatalogListingView } from "./catalog-listing-view";
import type { CatalogEmptyStateVariant } from "./catalog-empty-state";
import type { ProductCardProps } from "./product-card";

interface CatalogApiItem {
  slug: string;
  name: string;
  shortDescription: string | null;
  priceFrom: number;
  hasPriceRange: boolean;
  heroImageUrl: string | null;
  heroImageAlt: string | null;
}

interface CatalogApiResponse {
  items: CatalogApiItem[];
  page: number;
  limit: number;
  total: number;
  totalPages: number;
  filters: { models: string[]; colors: string[] };
}

export interface CatalogFiltersProps {
  initialItems: ProductCardProps[];
  initialFilters: { models: string[]; colors: string[] };
}

function toProductCardProps(item: CatalogApiItem): ProductCardProps {
  return {
    slug: item.slug,
    name: item.name,
    shortDescription: item.shortDescription,
    priceFrom: item.priceFrom,
    hasPriceRange: item.hasPriceRange,
    imageUrl: item.heroImageUrl,
    imageAlt: item.heroImageAlt ?? item.name,
  };
}

function buildSearchParams(params: {
  q: string;
  model: string;
  color: string;
  page: number;
}): URLSearchParams {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.model) search.set("model", params.model);
  if (params.color) search.set("color", params.color);
  if (params.page > 1) search.set("page", String(params.page));
  return search;
}

export function CatalogFilters({
  initialItems,
  initialFilters,
}: CatalogFiltersProps) {
  const [q, setQ] = useState("");
  const [model, setModel] = useState("");
  const [color, setColor] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<ProductCardProps[]>(initialItems);
  const [filters, setFilters] = useState(initialFilters);
  const [totalPages, setTotalPages] = useState(1);
  const [emptyStateVariant, setEmptyStateVariant] =
    useState<CatalogEmptyStateVariant | null>(null);
  const [isPending, setIsPending] = useState(false);

  const runSearch = useCallback(
    async (nextQ: string, nextModel: string, nextColor: string, nextPage: number) => {
      setIsPending(true);
      const search = buildSearchParams({
        q: nextQ,
        model: nextModel,
        color: nextColor,
        page: nextPage,
      });

      try {
        const query = search.toString();
        const response = await fetch(`/api/catalog${query ? `?${query}` : ""}`);
        if (!response.ok) {
          setItems([]);
          setEmptyStateVariant("error");
          return;
        }

        const data: CatalogApiResponse = await response.json();
        setItems(data.items.map(toProductCardProps));
        setFilters(data.filters);
        setTotalPages(data.totalPages);
        setEmptyStateVariant(data.items.length === 0 ? "no-results" : null);

        const url = new URL(window.location.href);
        url.search = query;
        window.history.replaceState(null, "", url.toString());
      } catch {
        setItems([]);
        setEmptyStateVariant("error");
      } finally {
        setIsPending(false);
      }
    },
    [],
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    void runSearch(q, model, color, 1);
  }

  function handleModelToggle(value: string) {
    const next = model === value ? "" : value;
    setModel(next);
    setPage(1);
    void runSearch(q, next, color, 1);
  }

  function handleColorToggle(value: string) {
    const next = color === value ? "" : value;
    setColor(next);
    setPage(1);
    void runSearch(q, model, next, 1);
  }

  function handlePageChange(nextPage: number) {
    setPage(nextPage);
    void runSearch(q, model, color, nextPage);
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-4 rounded-2xl bg-brand-blush/60 p-4 sm:p-5">
        <form
          onSubmit={handleSubmit}
          role="search"
          className="flex flex-wrap items-center gap-3"
        >
          <div className="relative min-w-[200px] flex-1">
            <Search
              aria-hidden="true"
              className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
            />
            <Input
              type="search"
              value={q}
              onChange={(event) => setQ(event.target.value)}
              placeholder="Buscar productos"
              aria-label="Buscar productos"
              className="rounded-full bg-background pl-9"
            />
          </div>
          <Button type="submit" className="rounded-full">
            Buscar
          </Button>
        </form>

        {(filters.models.length > 0 || filters.colors.length > 0) && (
          <div className="flex flex-col gap-3">
            {filters.models.length > 0 && (
              <div
                role="group"
                aria-label="Modelo"
                className="flex flex-wrap gap-2"
              >
                {filters.models.map((m) => (
                  <Chip
                    key={m}
                    pressed={model === m}
                    onPressedChange={() => handleModelToggle(m)}
                  >
                    {m}
                  </Chip>
                ))}
              </div>
            )}
            {filters.colors.length > 0 && (
              <div
                role="group"
                aria-label="Color"
                className="flex flex-wrap gap-2"
              >
                {filters.colors.map((c) => (
                  <Chip
                    key={c}
                    pressed={color === c}
                    onPressedChange={() => handleColorToggle(c)}
                    className="capitalize"
                  >
                    {c}
                  </Chip>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <CatalogListingView products={items} emptyStateVariant={emptyStateVariant} />

      {emptyStateVariant === null && items.length > 0 && totalPages > 1 && (
        <div className="flex items-center justify-center gap-4">
          <Button
            type="button"
            variant="outline"
            disabled={page <= 1 || isPending}
            onClick={() => handlePageChange(page - 1)}
          >
            Anterior
          </Button>
          <span className="text-sm text-muted-foreground">
            Página {page} de {totalPages}
          </span>
          <Button
            type="button"
            variant="outline"
            disabled={page >= totalPages || isPending}
            onClick={() => handlePageChange(page + 1)}
          >
            Siguiente
          </Button>
        </div>
      )}
    </div>
  );
}
