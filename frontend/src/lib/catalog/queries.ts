/**
 * Query builders against the public catalog views only. `catalogFrom()` is
 * the single `.from()` call site in this module — the `CatalogRelation`
 * type it accepts makes naming a base table a compile error — and every
 * `.select()` call below passes one of the three exported column
 * constants, never a literal string or `select("*")`. Enforced by the
 * source-grep test in `queries.test.ts`.
 *
 * Every read returns `{ ok: true, data } | { ok: false, reason }` instead
 * of throwing, so a build-time or request-time Supabase outage becomes a
 * first-class `error` UI state rather than a thrown exception.
 *
 * @see design.md "Query Shapes", "Structural Guarantee: cost / exact stock
 * unreachable".
 */
import type { SupabaseClient } from "@supabase/supabase-js";
import {
  CATALOG_IMAGE_COLUMNS,
  CATALOG_PRODUCT_COLUMNS,
  CATALOG_VARIANT_COLUMNS,
  type CatalogRelation,
} from "./columns";
import type {
  CatalogImageRow,
  CatalogProductRow,
  CatalogVariantRow,
} from "./types";

export type CatalogQueryResult<T> =
  | { ok: true; data: T }
  | { ok: false; reason: string };

/**
 * The only `.from()` call site in this module. `relation` is typed
 * `CatalogRelation` (see `columns.ts`), so naming a base table or the
 * internal-only `variant_stock_levels` view is a compile error.
 */
function catalogFrom(client: SupabaseClient, relation: CatalogRelation) {
  return client.from(relation);
}

function errorResult<T>(error: { message: string }): CatalogQueryResult<T> {
  return { ok: false, reason: error.message };
}

/**
 * Resolves an optional `model`/`color` filter to the set of product ids
 * whose variants match. Selects the full `CATALOG_VARIANT_COLUMNS` row
 * (never a bespoke `select("product_id")` literal — see the source-grep
 * guarantee) and extracts `product_id` in memory.
 *
 * Returns `data: null` when neither filter is supplied, meaning "no scope
 * — do not filter the listing query", distinct from `data: []` meaning
 * "scoped, but zero products match".
 */
export async function scopeProductIdsByVariant(
  client: SupabaseClient,
  filters: { model?: string | null; color?: string | null },
): Promise<CatalogQueryResult<string[] | null>> {
  const model = filters.model?.trim() || null;
  const color = filters.color?.trim() || null;

  if (!model && !color) {
    return { ok: true, data: null };
  }

  let query = catalogFrom(client, "catalog_variants").select(
    CATALOG_VARIANT_COLUMNS,
  );

  if (model) {
    query = query.eq("phone_model", model);
  }
  if (color) {
    query = query.eq("color", color);
  }

  const { data, error } = await query;
  if (error) {
    return errorResult(error);
  }

  const rows = (data ?? []) as CatalogVariantRow[];
  const ids = Array.from(new Set(rows.map((row) => row.product_id)));
  return { ok: true, data: ids };
}

export interface ListCatalogProductsParams {
  /** Sanitized search term, or `null`/empty to skip the name/description filter. */
  q?: string | null;
  /** Product-id scope from `scopeProductIdsByVariant`. `null` = no scope; `[]` = scoped to nothing. */
  productIds?: string[] | null;
  page: number;
  limit: number;
}

export interface ListCatalogProductsResult {
  products: CatalogProductRow[];
  total: number;
}

export async function listCatalogProducts(
  client: SupabaseClient,
  params: ListCatalogProductsParams,
): Promise<CatalogQueryResult<ListCatalogProductsResult>> {
  const { q, productIds, page, limit } = params;

  // A resolved-but-empty scope means "matches nothing" — short-circuit
  // without issuing a query, matching the design's well-formed-empty-result
  // contract for an unknown model/color filter.
  if (productIds !== null && productIds !== undefined && productIds.length === 0) {
    return { ok: true, data: { products: [], total: 0 } };
  }

  let query = catalogFrom(client, "catalog_products").select(
    CATALOG_PRODUCT_COLUMNS,
    { count: "exact" },
  );

  if (productIds && productIds.length > 0) {
    query = query.in("id", productIds);
  }

  const trimmedQ = q?.trim();
  if (trimmedQ) {
    query = query.or(
      `name.ilike.%${trimmedQ}%,description.ilike.%${trimmedQ}%`,
    );
  }

  const offset = (page - 1) * limit;
  query = query
    .order("created_at", { ascending: false })
    .range(offset, offset + limit - 1);

  const { data, error, count } = await query;
  if (error) {
    return errorResult(error);
  }

  return {
    ok: true,
    data: {
      products: (data ?? []) as CatalogProductRow[],
      total: count ?? 0,
    },
  };
}

export async function listVariantsForProducts(
  client: SupabaseClient,
  productIds: string[],
): Promise<CatalogQueryResult<CatalogVariantRow[]>> {
  if (productIds.length === 0) {
    return { ok: true, data: [] };
  }

  const { data, error } = await catalogFrom(client, "catalog_variants")
    .select(CATALOG_VARIANT_COLUMNS)
    .in("product_id", productIds)
    .order("color");

  if (error) {
    return errorResult(error);
  }

  return { ok: true, data: (data ?? []) as CatalogVariantRow[] };
}

export async function listImagesForProducts(
  client: SupabaseClient,
  productIds: string[],
): Promise<CatalogQueryResult<CatalogImageRow[]>> {
  if (productIds.length === 0) {
    return { ok: true, data: [] };
  }

  const { data, error } = await catalogFrom(client, "catalog_product_images")
    .select(CATALOG_IMAGE_COLUMNS)
    .in("product_id", productIds)
    .order("sort_order");

  if (error) {
    return errorResult(error);
  }

  return { ok: true, data: (data ?? []) as CatalogImageRow[] };
}

export async function getCatalogProductBySlug(
  client: SupabaseClient,
  slug: string,
): Promise<CatalogQueryResult<CatalogProductRow | null>> {
  const { data, error } = await catalogFrom(client, "catalog_products")
    .select(CATALOG_PRODUCT_COLUMNS)
    .eq("slug", slug)
    .maybeSingle();

  if (error) {
    return errorResult(error);
  }

  return { ok: true, data: (data ?? null) as CatalogProductRow | null };
}

export interface CatalogFilterOptions {
  models: string[];
  colors: string[];
}

/**
 * Selects the full `CATALOG_VARIANT_COLUMNS` row (not a bespoke
 * `"phone_model,color"` literal — see the source-grep guarantee) and
 * dedupes/sorts `phone_model`/`color` in memory.
 */
export async function getCatalogFilterOptions(
  client: SupabaseClient,
): Promise<CatalogQueryResult<CatalogFilterOptions>> {
  const { data, error } = await catalogFrom(client, "catalog_variants").select(
    CATALOG_VARIANT_COLUMNS,
  );

  if (error) {
    return errorResult(error);
  }

  const rows = (data ?? []) as CatalogVariantRow[];
  const models = Array.from(new Set(rows.map((row) => row.phone_model))).sort();
  const colors = Array.from(new Set(rows.map((row) => row.color))).sort();

  return { ok: true, data: { models, colors } };
}
