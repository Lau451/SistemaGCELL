# Tasks: Supabase Schema — Products, Variants, Stock Ledger, Photo Storage

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~300-420 (4 migrations ~205, seed.sql ~55, config.toml ~8, rls_checks.sql ~85) |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR; fallback if actual diff exceeds 400: PR1 = migrations 1-2 (base tables + ledger), PR2 = migration 3-4 + seed + config + test (RLS/views/storage) |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main (cached, unused unless fallback split triggers) |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Base tables + ledger (migrations 1-2) | PR 1 (or single PR) | `psql -f supabase/tests/rls_checks.sql` (partial) | `supabase db reset` | Delete migration files 1-2, `supabase db reset` |
| 2 | RLS/views/storage/seed (migrations 3-4 + seed + config + test) | PR 2 (or single PR) | `psql -f supabase/tests/rls_checks.sql` (full) | `supabase db reset` | Delete migration files 3-4, seed.sql, config block, `supabase db reset` |

## Phase 1: RED — Author Failing Assertions

- [ ] 1.1 Create `supabase/tests/rls_checks.sql`: anon-denied asserts on `products`/`product_variants`/`product_images`/`stock_movements`; column-list asserts on `catalog_products`/`catalog_variants`/`catalog_product_images` (no `cost`, no quantity); append-only UPDATE/DELETE-raises assert; `in_stock` derivation assert (+10,-3,+2 -> stock=9).
- [ ] 1.2 Run `supabase db reset`, then `psql -f supabase/tests/rls_checks.sql`; confirm it fails (RED) — no schema exists yet.

## Phase 2: Base Catalog Schema (Migration 1)

- [ ] 2.1 `supabase migration new products_catalog`.
- [ ] 2.2 Create `products` (uuid PK, `slug` UNIQUE + format/length CHECK, `name`/`model` not-blank CHECK).
- [ ] 2.3 Create `product_variants` (FK `products`, `color`, `price`/`cost` numeric(10,2) CHECK >=0, composite UNIQUE `(product_id, id)`).
- [ ] 2.4 Create `product_images` (composite FK `(product_id, variant_id)` -> `product_variants`, FK `product_id` -> `products`, nullable `variant_id`).
- [ ] 2.5 Add `set_updated_at()` trigger fn + `BEFORE UPDATE` triggers on `products`/`product_variants`.

## Phase 3: Inventory Ledger (Migration 2)

- [ ] 3.1 `supabase migration new stock_movements_ledger`.
- [ ] 3.2 Create `stock_movements` (FK `product_variants` ON DELETE RESTRICT, `movement_type` CHECK in 5 values, `quantity_delta <> 0` CHECK, per-type sign-direction CHECK).
- [ ] 3.3 Add covering index `(variant_id) INCLUDE (quantity_delta)`.
- [ ] 3.4 Add `reject_stock_movements_mutation()` fn + `BEFORE UPDATE OR DELETE` trigger enforcing append-only.

## Phase 4: RLS + Public Views (Migration 3)

- [ ] 4.1 `supabase migration new public_catalog_rls`.
- [ ] 4.2 `ENABLE ROW LEVEL SECURITY` on all 4 base tables; zero anon/authenticated policies.
- [ ] 4.3 Create internal view `variant_stock_levels` (`SUM(quantity_delta)` per variant); no anon GRANT.
- [ ] 4.4 Create `catalog_products`, `catalog_variants` (`COALESCE(sl.quantity_on_hand,0) > 0 AS in_stock`), `catalog_product_images` views, `security_invoker = off`.
- [ ] 4.5 GRANT base tables to `service_role` (full CRUD; `stock_movements` SELECT+INSERT only); GRANT catalog views SELECT to `anon`, `authenticated`.

## Phase 5: Storage Bucket (Migration 4)

- [ ] 5.1 `supabase migration new storage_product_photos`.
- [ ] 5.2 Idempotent `INSERT INTO storage.buckets ... ON CONFLICT (id) DO NOTHING` for `product-photos`.
- [ ] 5.3 Add one `anon` SELECT policy on `storage.objects` scoped to the bucket; zero write policies.

## Phase 6: Seed + Config Wiring

- [ ] 6.1 Update `supabase/config.toml`: add `[storage.buckets.product-photos]` (`public = true`, `file_size_limit = "5MiB"`, jpeg/png/webp).
- [ ] 6.2 Create `supabase/seed.sql`: 2 products, ~4 variants, images, restock movements proving `in_stock` both ways.

## Phase 7: GREEN — Verify and Regress

- [ ] 7.1 `supabase db reset`; confirm all 4 migrations + seed apply clean, no errors.
- [ ] 7.2 Re-run `psql -f supabase/tests/rls_checks.sql`; confirm every assertion now passes (GREEN).
- [ ] 7.3 Run `npm --prefix frontend test` and `uv run --project backend pytest -q`; confirm both stay green.
