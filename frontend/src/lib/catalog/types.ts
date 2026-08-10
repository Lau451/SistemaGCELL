/**
 * Row shapes matching the public catalog views column-for-column
 * (`lib/catalog/columns.ts`). No `cost` or exact-stock-quantity field
 * exists on any of these types because none exists on the underlying view.
 *
 * @see supabase/migrations/20260810000458_public_catalog_rls.sql
 */

export interface CatalogProductRow {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  created_at: string;
}

export interface CatalogVariantRow {
  id: string;
  product_id: string;
  phone_model: string;
  color: string;
  price: number;
  in_stock: boolean;
}

export interface CatalogImageRow {
  id: string;
  product_id: string;
  /** NULL = product hero image; non-null = colour-specific image. */
  variant_id: string | null;
  storage_path: string;
  alt_text: string | null;
  sort_order: number;
}
