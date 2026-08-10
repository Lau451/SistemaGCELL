-- RLS lockdown of the four base tables plus the public catalog views that
-- are the only sanctioned public read path. `auto_expose_new_tables` is
-- unset in config.toml (not auto-exposed), so every table AND every view
-- below needs an explicit GRANT — a missing GRANT is a hard empty/error,
-- not a silent leak.

alter table products enable row level security;
alter table product_variants enable row level security;
alter table product_images enable row level security;
alter table stock_movements enable row level security;
-- Deliberately zero CREATE POLICY statements for anon/authenticated: the
-- views below are the entire public read surface.

-- Internal-only aggregate: no anon/authenticated GRANT. Live SUM() over
-- a covering index; a materialized rollup can replace this view later
-- without touching its callers if volume ever demands it.
create view variant_stock_levels
with (security_invoker = false) as
select
  variant_id,
  sum(quantity_delta)::integer as quantity_on_hand
from stock_movements
group by variant_id;

create view catalog_products
with (security_invoker = false) as
select
  id,
  slug,
  name,
  description,
  created_at
from products;

create view catalog_variants
with (security_invoker = false) as
select
  v.id,
  v.product_id,
  p.model as phone_model,
  v.color,
  v.price,
  -- LEFT JOIN yields NULL for a variant with zero movements; COALESCE
  -- turns that into false instead of an unusable NULL.
  coalesce(sl.quantity_on_hand, 0) > 0 as in_stock
from product_variants v
join products p on p.id = v.product_id
left join variant_stock_levels sl on sl.variant_id = v.id;

create view catalog_product_images
with (security_invoker = false) as
select
  id,
  product_id,
  variant_id,
  storage_path,
  alt_text,
  sort_order
from product_images;

-- Base tables: service_role only (bypasses RLS via BYPASSRLS, but still
-- needs an explicit GRANT because nothing is auto-exposed).
grant select, insert, update, delete on products, product_variants, product_images to service_role;
-- stock_movements is append-only: no UPDATE/DELETE grant, ever.
grant select, insert on stock_movements to service_role;

-- Public catalog views: the only anon/authenticated read surface.
grant select on catalog_products, catalog_variants, catalog_product_images to anon, authenticated;
