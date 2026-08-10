# Apply Progress: supabase-schema

**Mode**: Strict TDD (RED-first psql assertion script, pgTAP explicitly rejected per design's Testing Strategy)
**Branch**: `supabase-schema` (single PR, no chaining, per tasks' Review Workload Forecast)
**Status**: 24/24 tasks complete. Ready for verify.

## TDD Cycle Evidence

| Cycle | Action | Command | Result |
|---|---|---|---|
| RED | Author `supabase/tests/rls_checks.sql` (task 1.1) before any migration exists | — | File created: 324 lines, fixture + 6 assertion groups |
| RED | Genuine failing run against an empty schema (task 1.2) | `supabase db reset` (migrations + seed.sql temporarily relocated to scratchpad) then `docker exec -i supabase_db_SistemaGCELL psql -U postgres -d postgres -v ON_ERROR_STOP=1 < supabase/tests/rls_checks.sql` | `ERROR: relation "products" does not exist` — exit code 3. Genuine RED: assertions fail on missing relations, not on a false assertion path. |
| GREEN | Migrations + seed restored, then `supabase db reset` (task 7.1) | `supabase db reset` | All 4 migrations + `seed.sql` applied clean, no errors |
| GREEN | Re-run the identical script (task 7.2) | `docker exec -i supabase_db_SistemaGCELL psql -U postgres -d postgres -v ON_ERROR_STOP=1 < supabase/tests/rls_checks.sql` | `ALL ASSERTIONS PASSED` — exit code 0. Every assertion (anon-denied x4, column-list x3, anon-read-via-view, stock derivation 9, in_stock true/false, UPDATE-rejected, DELETE-rejected, service_role reads cost) passed. |
| REFACTOR | N/A this change — single macro RED/GREEN cycle per design's Testing Strategy (one script, not per-migration incremental TDD) | — | No refactor needed; migrations match design DDL shapes as authored |

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `docker exec -i supabase_db_SistemaGCELL psql -U postgres -d postgres -v ON_ERROR_STOP=1 < supabase/tests/rls_checks.sql` — exit 0, `ALL ASSERTIONS PASSED` (14 PASS notices + 1 summary notice) |
| Runtime harness command/scenario and exact result | `supabase db reset` (task 7.1) — Docker Desktop 29.6.2 confirmed running; all 4 CLI-timestamped migrations + `seed.sql` applied cleanly on a fresh container, no errors |
| Rollback boundary | Delete `supabase/migrations/2026081000{0449,0453,0458,0502}_*.sql`, `supabase/seed.sql`, `supabase/tests/rls_checks.sql`, revert the `[storage.buckets.product-photos]` block in `supabase/config.toml`, then `supabase db reset` |

## Regression Evidence (task 7.3)

| Suite | Command | Result |
|---|---|---|
| Frontend | `npm --prefix frontend test` | 2 test files, 7 tests passed |
| Backend | `uv run --project backend pytest -q` | 9 passed, 1 pre-existing unrelated deprecation warning (httpx/starlette) |

## Completed Tasks (24/24)

### Phase 1: RED — Author Failing Assertions
- [x] 1.1 `supabase/tests/rls_checks.sql` created
- [x] 1.2 RED confirmed against empty schema

### Phase 2: Base Catalog Schema (Migration 1)
- [x] 2.1 `supabase migration new products_catalog` → `supabase/migrations/20260810000449_products_catalog.sql`
- [x] 2.2 `products` table (uuid PK, slug UNIQUE + format/length CHECK, name/model not-blank CHECK)
- [x] 2.3 `product_variants` table (FK products, color, price/cost numeric(10,2) >=0, composite UNIQUE (product_id, id))
- [x] 2.4 `product_images` table (composite FK (product_id, variant_id) -> product_variants, FK product_id -> products, nullable variant_id)
- [x] 2.5 `set_updated_at()` trigger fn + BEFORE UPDATE triggers on products/product_variants

### Phase 3: Inventory Ledger (Migration 2)
- [x] 3.1 `supabase migration new stock_movements_ledger` → `supabase/migrations/20260810000453_stock_movements_ledger.sql`
- [x] 3.2 `stock_movements` table (FK product_variants ON DELETE RESTRICT, movement_type CHECK in 5 values, quantity_delta <> 0 CHECK, sign-direction CHECK)
- [x] 3.3 Covering index `(variant_id) INCLUDE (quantity_delta)`
- [x] 3.4 `reject_stock_movements_mutation()` fn + BEFORE UPDATE OR DELETE trigger

### Phase 4: RLS + Public Views (Migration 3)
- [x] 4.1 `supabase migration new public_catalog_rls` → `supabase/migrations/20260810000458_public_catalog_rls.sql`
- [x] 4.2 RLS enabled on all 4 base tables, zero anon/authenticated policies
- [x] 4.3 `variant_stock_levels` internal view, no anon GRANT
- [x] 4.4 `catalog_products`, `catalog_variants` (in_stock via COALESCE), `catalog_product_images` views, `security_invoker = false`
- [x] 4.5 GRANTs: base tables → service_role (stock_movements SELECT+INSERT only); catalog views → anon, authenticated (SELECT)

### Phase 5: Storage Bucket (Migration 4)
- [x] 5.1 `supabase migration new storage_product_photos` → `supabase/migrations/20260810000502_storage_product_photos.sql`
- [x] 5.2 Idempotent bucket insert (`ON CONFLICT (id) DO NOTHING`)
- [x] 5.3 One anon SELECT policy on storage.objects, zero write policies

### Phase 6: Seed + Config Wiring
- [x] 6.1 `supabase/config.toml`: `[storage.buckets.product-photos]` block added
- [x] 6.2 `supabase/seed.sql`: 2 products, 4 variants, 4 images, stock movements proving in_stock both ways (plus 2 no-movement variants)

### Phase 7: GREEN — Verify and Regress
- [x] 7.1 `supabase db reset` — all migrations + seed apply clean
- [x] 7.2 `rls_checks.sql` re-run — GREEN, all assertions pass
- [x] 7.3 Frontend + backend suites stay green

## Files Changed

| File | Action | What Was Done |
|---|---|---|
| `supabase/tests/rls_checks.sql` | Created | RED-first psql/PL-pgSQL assertion script (324 lines): idempotent fixture, anon-denied x4, view column-list x3, anon-read-via-view, stock derivation (9 from +10,-3,+2), in_stock true/false, append-only UPDATE/DELETE rejection, service_role full access |
| `supabase/migrations/20260810000449_products_catalog.sql` | Created | `products`, `product_variants`, `product_images` base tables + `set_updated_at()` trigger fn |
| `supabase/migrations/20260810000453_stock_movements_ledger.sql` | Created | `stock_movements` append-only ledger, covering index, `reject_stock_movements_mutation()` trigger |
| `supabase/migrations/20260810000458_public_catalog_rls.sql` | Created | RLS enable (0 policies) on 4 base tables; `variant_stock_levels`, `catalog_products`, `catalog_variants`, `catalog_product_images` views; all GRANTs |
| `supabase/migrations/20260810000502_storage_product_photos.sql` | Created | Idempotent `product-photos` bucket insert + anon SELECT storage policy |
| `supabase/seed.sql` | Created | Dev fixture: 2 products, 4 variants, 4 images, stock movements (both in_stock states) |
| `supabase/config.toml` | Modified | Added `[storage.buckets.product-photos]` (public=true, 5MiB, jpeg/png/webp) |
| `openspec/changes/supabase-schema/tasks.md` | Modified | All 24 tasks marked `[x]` |

## Deviations from Design

1. `stock_movements.id` uses `bigint generated always as identity` — design did not specify an explicit PK type for the ledger table. Chosen over `uuid` because the ledger is internal-only (never exposed to `anon`/`authenticated` directly, only via the `variant_stock_levels` aggregate), and a monotonic identity column is a natural fit for an append-only audit log. This does not affect any spec requirement or the public view contract.
2. `catalog_variants.phone_model` (aliased from `products.model` via a join) matches the design's Data Flow "Exposed columns" list exactly — flagging it here only because it required joining `products` inside the view (not purely `product_variants` columns), which the Architecture Decisions table didn't spell out as a join. Implemented as documented in Data Flow.
3. Otherwise implementation matches design precisely: RLS pattern (Decision 1/2), `movement_type` CHECK not enum (Decision 3), live `SUM()` not materialized (Decision 4), `COALESCE` for `in_stock` (Decision 5), trigger + GRANT append-only (Decision 6), `ON DELETE RESTRICT` on the ledger FK (Decision 7), slug format/length CHECK (Decision 8), `numeric(10,2)` money (Decision 9), composite FK image ownership shape (Decision 10, used verbatim), zero storage write policies (Decision 11).

## Issues Found

1. **Docker/Supabase CLI risk resolved**: Docker Desktop 29.6.2 confirmed running; `npx supabase start`/`db reset` both work without issue on this Windows host. First `supabase start` took several minutes (one-time image pull of the full Supabase Docker stack — postgres, gotrue, kong, storage-api, realtime, etc., ~10 images). No blocker.
2. **`psql` is not installed on the Windows host** (`which psql` → not found; `npx supabase` bundles no psql). Worked around by running assertions via `docker exec -i supabase_db_SistemaGCELL psql -U postgres -d postgres -v ON_ERROR_STOP=1 < supabase/tests/rls_checks.sql` against the running local Postgres container instead of a host-installed `psql` binary. This is the correct long-term way to invoke this script on this host and should be the documented command going forward (not a literal host `psql` binary).
3. **Genuine RED required temporarily relocating drafted migration files**: because `supabase migration new` (task 2.1/3.1/4.1/5.1) was run early to reserve strictly-ascending CLI timestamps while Docker images were still pulling, and migration content was drafted in parallel to save time, the 4 migration files and `seed.sql` were moved to the session scratchpad before the RED `db reset`, then restored before the GREEN `db reset`. This preserved a truly empty schema for the RED assertion run (confirmed by the `relation "products" does not exist` error) without discarding any drafted work.
4. **Actual diff size (588 lines: `supabase/config.toml` +5, 4 migrations +76/+43/+68/+13, `seed.sql` +59, `rls_checks.sql` +324) exceeds the tasks' forecast estimate (~300-420) and the 400-line review budget**, driven almost entirely by the RED-first assertion script itself (324 of 588 lines) — a test artifact, not application/schema logic. Per the explicit instruction for this batch, this remains a single PR (no chaining); flagging the overage for the reviewer/orchestrator rather than silently splitting.

## Workload / PR Boundary

- Mode: single PR (no chaining), per tasks' Review Workload Forecast and explicit apply-batch instruction
- Current work unit: both suggested work units (1: base tables + ledger; 2: RLS/views/storage/seed) completed together in this one branch
- Boundary: start = empty `supabase/` schema state (only `config.toml`/`.gitignore` from `initial-scaffolding`); end = all 4 migrations + seed + test script + config wiring, GREEN-verified
- Estimated review budget impact: actual diff (588 lines) is ~40% over the 400-line budget and above the ~300-420 forecast range; see Issues Found #4
