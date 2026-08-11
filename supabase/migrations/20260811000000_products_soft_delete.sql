-- Additive soft-delete for products/product_variants. Nullable `deleted_at`,
-- no default: metadata-only ALTER, no table rewrite. `NULL` = active,
-- non-NULL = retired at that instant. `stock_movements` gets nothing --
-- it is only ever read, never soft-deleted.
--
-- The three public catalog views are replaced with CREATE OR REPLACE VIEW:
-- identical column lists/types/order to 20260810000458_public_catalog_rls.sql
-- (frontend/src/lib/catalog/columns.ts pins these), only a WHERE addition.
-- `products_slug_key` stays a plain global unique constraint (not partial) --
-- see design.md "retired slugs stay reserved".

alter table products add column deleted_at timestamptz;
alter table product_variants add column deleted_at timestamptz;

create index products_active_idx on products (created_at, id) where deleted_at is null;
create index product_variants_active_product_idx on product_variants (product_id) where deleted_at is null;

create or replace view catalog_products
with (security_invoker = false) as
select
  id,
  slug,
  name,
  description,
  created_at
from products
where deleted_at is null;

create or replace view catalog_variants
with (security_invoker = false) as
select
  v.id,
  v.product_id,
  p.model as phone_model,
  v.color,
  v.price,
  coalesce(sl.quantity_on_hand, 0) > 0 as in_stock
from product_variants v
join products p on p.id = v.product_id
left join variant_stock_levels sl on sl.variant_id = v.id
where v.deleted_at is null and p.deleted_at is null;

create or replace view catalog_product_images
with (security_invoker = false) as
select
  i.id,
  i.product_id,
  i.variant_id,
  i.storage_path,
  i.alt_text,
  i.sort_order
from product_images i
join products p on p.id = i.product_id
where p.deleted_at is null
  and (
    i.variant_id is null
    or exists (
      select 1 from product_variants v
      where v.id = i.variant_id and v.deleted_at is null
    )
  );
