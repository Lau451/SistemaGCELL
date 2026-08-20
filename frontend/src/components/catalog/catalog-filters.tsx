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

  function handleModelChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const value = event.target.value;
    setModel(value);
    setPage(1);
    void runSearch(q, value, color, 1);
  }

  function handleColorChange(event: React.ChangeEvent<HTMLSelectElement>) {
    const value = event.target.value;
    setColor(value);
    setPage(1);
    void runSearch(q, model, value, 1);
  }

  function handlePageChange(nextPage: number) {
    setPage(nextPage);
    void runSearch(q, model, color, nextPage);
  }

  return (
    <div className="flex flex-col gap-6">
      <form
        onSubmit={handleSubmit}
        role="search"
        className="flex flex-wrap items-center gap-3"
      >
        <input
          type="search"
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="Buscar productos"
          aria-label="Buscar productos"
          className="border-border rounded-md border px-3 py-2 text-sm"
        />
        <select
          aria-label="Modelo"
          value={model}
          onChange={handleModelChange}
          className="border-border rounded-md border px-3 py-2 text-sm"
        >
          <option value="">Todos los modelos</option>
          {filters.models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
        <select
          aria-label="Color"
          value={color}
          onChange={handleColorChange}
          className="border-border rounded-md border px-3 py-2 text-sm capitalize"
        >
          <option value="">Todos los colores</option>
          {filters.colors.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <button
          type="submit"
          className="bg-primary text-primary-foreground rounded-md px-4 py-2 text-sm font-medium"
        >
          Buscar
        </button>
      </form>

      <CatalogListingView products={items} emptyStateVariant={emptyStateVariant} />

      {emptyStateVariant === null && items.length > 0 && totalPages > 1 && (
        <div className="flex items-center justify-center gap-4">
          <button
            type="button"
            disabled={page <= 1 || isPending}
            onClick={() => handlePageChange(page - 1)}
            className="border-border rounded-md border px-3 py-1.5 text-sm disabled:opacity-50"
          >
            Anterior
          </button>
          <span className="text-muted-foreground text-sm">
            Página {page} de {totalPages}
          </span>
          <button
            type="button"
            disabled={page >= totalPages || isPending}
            onClick={() => handlePageChange(page + 1)}
            className="border-border rounded-md border px-3 py-1.5 text-sm disabled:opacity-50"
          >
            Siguiente
          </button>
        </div>
      )}
    </div>
  );
}
