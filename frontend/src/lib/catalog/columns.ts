/**
 * Typed allowlist of the public catalog views. Every query builder in
 * `lib/catalog/queries.ts` MUST call `.from()` with one of these values —
 * naming a base table (`products`, `product_variants`, `product_images`) or
 * the internal-only `variant_stock_levels` view is a compile error.
 *
 * @see supabase/migrations/20260810000458_public_catalog_rls.sql
 */
export const CATALOG_RELATIONS = [
  "catalog_products",
  "catalog_variants",
  "catalog_product_images",
] as const;

export type CatalogRelation = (typeof CATALOG_RELATIONS)[number];

/**
 * Explicit column lists, one per view, exactly matching the columns each
 * view actually selects in the migration above. `select("*")` is never used
 * anywhere in this codebase — every `.select()` call must pass one of these
 * constants, which a source-grep test (`queries.test.ts`, Phase 2) enforces.
 */
export const CATALOG_PRODUCT_COLUMNS =
  "id,slug,name,description,created_at" as const;

export const CATALOG_VARIANT_COLUMNS =
  "id,product_id,phone_model,color,price,in_stock" as const;

export const CATALOG_IMAGE_COLUMNS =
  "id,product_id,variant_id,storage_path,alt_text,sort_order" as const;
