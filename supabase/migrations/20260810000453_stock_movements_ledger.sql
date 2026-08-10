-- Append-only inventory ledger. Current stock is always the derived
-- SUM(quantity_delta) per variant (see variant_stock_levels in the RLS
-- migration) — never a stored, mutable counter.

create table stock_movements (
  id bigint generated always as identity primary key,
  variant_id uuid not null references product_variants (id) on delete restrict,
  movement_type text not null,
  quantity_delta integer not null,
  reason text,
  created_at timestamptz not null default now(),
  constraint stock_movements_movement_type_check
    check (movement_type in ('restock', 'sale', 'return', 'breakage', 'adjustment')),
  constraint stock_movements_quantity_delta_nonzero_check
    check (quantity_delta <> 0),
  -- restock/return must add stock, sale/breakage must remove stock;
  -- adjustment is the escape hatch and may go either direction.
  constraint stock_movements_sign_direction_check check (
    (movement_type in ('restock', 'return') and quantity_delta > 0)
    or (movement_type in ('sale', 'breakage') and quantity_delta < 0)
    or (movement_type = 'adjustment')
  )
);

-- Covering index: SUM(quantity_delta) per variant is served entirely from
-- the index without a heap fetch.
create index stock_movements_variant_id_covering_idx
  on stock_movements (variant_id) include (quantity_delta);

create or replace function reject_stock_movements_mutation()
returns trigger
language plpgsql
as $$
begin
  raise exception 'stock_movements is append-only: % is not permitted', tg_op;
end;
$$;

-- GRANT alone does not bind a direct postgres/superuser connection, so
-- append-only is enforced as a schema invariant via trigger, not GRANT only.
create trigger stock_movements_reject_mutation
  before update or delete on stock_movements
  for each row execute function reject_stock_movements_mutation();
