-- Additive short-description blurb for products (content-ai-domains D3/DD7,
-- PR 1 of the chain). Nullable `short_description`, no default:
-- metadata-only ALTER, no table rewrite, exactly like
-- 20260811000000_products_soft_delete.sql's `deleted_at`.
--
-- `products.description` is unchanged and reused in *meaning only* as the
-- long detail body -- no rename, no backfill.
--
-- `catalog_products` is replaced with CREATE OR REPLACE VIEW, which can
-- only APPEND columns -- short_description lands after created_at. This
-- preserves the anon/authenticated GRANT issued in
-- 20260810000458_public_catalog_rls.sql; DROP VIEW ... CASCADE would not
-- (DD7).

alter table products add column short_description text;

create or replace view catalog_products
with (security_invoker = false) as
select
  id,
  slug,
  name,
  description,
  created_at,
  short_description
from products
where deleted_at is null;
