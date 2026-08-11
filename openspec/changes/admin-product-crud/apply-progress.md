# Apply Progress: Admin Product CRUD

## Batch 1 (PR1 — Migration + Read Filters)

**Scope**: Phase 0 (0.1–0.2) + Phase 1 (1.1–1.6), the pre-resolved "PR 1"
work unit (`chain strategy: stacked-to-main`, `delivery strategy:
ask-on-risk`) from `tasks.md`'s Review Workload Forecast. Branch
`pr1-product-crud-migration-read-filters` off `main` (`f14ec39`). No port/
adapter method additions beyond the three existing SELECTs' read filters, no
API routes, no frontend — that scope is explicitly out for PR2–PR4.
**Mode**: Strict TDD.

### Completed Tasks

- [x] 0.1 Confirmed local Supabase stack up (`npx supabase status`) — core
      services (DB, Auth, REST, Studio) running
- [x] 0.2 Picked migration filename timestamp `20260811000000` (sorts after
      `20260810000502`, follows the repo's `YYYYMMDDHHMMSS_snake_case.sql`
      convention)
- [x] 1.1 Created `supabase/migrations/20260811000000_products_soft_delete.sql`
      — `deleted_at timestamptz` on `products` and `product_variants`
      (nullable, no default), `products_active_idx` and
      `product_variants_active_product_idx` partial indexes; applied via
      `npx supabase migration up`
- [x] 1.2 Same migration: `CREATE OR REPLACE VIEW` for `catalog_products`,
      `catalog_variants`, `catalog_product_images` — identical column
      lists/types/order to `20260810000458_public_catalog_rls.sql`, only a
      `WHERE ... deleted_at IS NULL` addition (cascade via
      `p.deleted_at IS NULL` on the variants/images views)
- [x] 1.3 RED `backend/tests/integration/db/test_product_repository.py`
      (extend) — the `ON`-vs-`WHERE` trap
- [x] 1.4 GREEN `backend/src/gcell/products/infrastructure/postgres_product_repository.py`
      — `deleted_at IS NULL` filters added
- [x] 1.5 RED (proven) + tests `backend/tests/integration/db/test_catalog_soft_delete_views.py`
      (new) — view-level soft-delete exclusion
- [x] 1.6 Regression — public-catalog frontend tests + full backend/frontend
      suites confirmed green, unmodified

## Files Changed

| File | Action | What Was Done |
|---|---|---|
| `supabase/migrations/20260811000000_products_soft_delete.sql` | Created | `deleted_at timestamptz` on `products`/`product_variants` (nullable, no default); `products_active_idx` (`created_at, id` where `deleted_at is null`); `product_variants_active_product_idx` (`product_id` where `deleted_at is null`); `CREATE OR REPLACE VIEW` for all 3 catalog views with an added `WHERE`/`ON`-cascade filter, identical column lists to the prior migration |
| `backend/src/gcell/products/infrastructure/postgres_product_repository.py` | Modified | `_SELECT_BY_SLUG`/`_SELECT_BY_ID`/`_SELECT_ALL`: added `p.deleted_at IS NULL` to each `WHERE`; added `AND v.deleted_at IS NULL` to each `LEFT JOIN product_variants v ON ...` — the variant filter is in `ON`, never `WHERE`, per design.md's explicit warning |
| `backend/tests/integration/db/test_product_repository.py` | Modified | Added `test_list_all_keeps_product_with_every_variant_retired` — the `ON`-vs-`WHERE` trap RED/GREEN test |
| `backend/tests/integration/db/test_catalog_soft_delete_views.py` | Created | 3 tests: product retirement removes it from all 3 catalog views (incl. hero + variant images); retiring one variant hides only that variant and its image while siblings/hero survive; a live untouched product is unaffected by a sibling's retirement |
| `openspec/changes/admin-product-crud/tasks.md` | Modified | Phase 0 + Phase 1 tasks marked `[x]` with DONE notes |

## TDD Cycle Evidence (Strict TDD Mode)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.3/1.4 | `test_product_repository.py` | Integration (`db_conn`) | Pre-existing 10/10 tests in this file stayed green throughout | Written and run: FAILED — retired variant still returned in `fetched.variants` (adapter reads unfiltered rows pre-fix) | Passed 11/11 in the file after adding `deleted_at IS NULL` filters | N/A — single case is the entire threat (the `ON`-vs-`WHERE` degradation) | Clean, no further change needed |
| 1.5 | `test_catalog_soft_delete_views.py` | Integration (`db_conn`) | N/A (new file) | Proven via a separate, non-destructive proof: replayed the pre-migration view SQL inside a transaction rolled back at the end, confirmed a retired product's row still leaked through `catalog_products` under the OLD definitions | All 3 tests pass against the real, already-migrated view definitions | 3 distinct cases: full-product retirement, single-variant retirement (siblings + hero image survive), live-product non-interference | Clean |

### Test Summary
- **Total tests written this batch**: 4 new (1 repository trap test + 3 view tests)
- **Total tests passing (backend, full suite, no filter)**: 102/102
- **Total tests passing (frontend, full suite, no filter)**: 170/170 (30 files)
- **Layers used**: Integration only (this batch has no application/domain surface — read-side SQL filters only)
- **Approval tests**: None
- **Pure functions created**: None — pure SQL/adapter-filter change

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd backend && uv run pytest tests/integration/db/test_product_repository.py tests/integration/db/test_catalog_soft_delete_views.py -v` (with `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres`) → **14 passed** |
| Runtime harness command/scenario and exact result | `npx supabase migration up` against the real local Postgres → applied cleanly; verified via a direct `asyncpg` script: `deleted_at` present on both tables, both partial indexes present with the correct `WHERE` predicate, all 3 view column lists byte-identical to `frontend/src/lib/catalog/columns.ts`. Separately, RED proof for the view filter: replayed the pre-migration `CREATE OR REPLACE VIEW` definitions inside a transaction that was rolled back, confirmed a retired product row was NOT filtered under the old definitions, confirmed no lasting schema change after rollback |
| Rollback boundary | Revert `supabase/migrations/20260811000000_products_soft_delete.sql` (additive: `alter table ... drop column deleted_at` + re-run the two prior view definitions from `20260810000458_public_catalog_rls.sql`, per design.md's documented rollback) and the `WHERE`/`ON` diff in `postgres_product_repository.py`; delete `test_catalog_soft_delete_views.py` and the one added test in `test_product_repository.py`. No product, variant, image, or stock row is ever destroyed by the forward path |

## Diff Size (measured, `git diff --stat` with intent-to-add for new files)

4 files changed, 276 insertions(+), 5 deletions(-) — **281 authored changed
lines**, within the 400-line budget (`tasks.md`'s own estimate for this
work unit was `~200`; the 3-test view file plus the trap test's docstring
pushed it to 281, still comfortably under budget and the smallest of the
4 planned PR slices).

## Deviations from Design

None. The migration SQL is byte-for-byte design.md's "Migration (the only
view-safe shape)" block; the repository filter placement (`ON` for the
variant join, `WHERE` for the product row) matches design.md's explicit
"the `LEFT JOIN` filter goes in `ON`, never in `WHERE`" decision exactly.

## Issues Found

None. One design assumption was worth stress-testing rather than accepting
on faith: whether the `ON`-vs-`WHERE` trap would actually reproduce against
the pre-fix adapter. It did — task 1.3's RED run failed with the retired
variant still present in `fetched.variants`, confirming the adapter read
every row unfiltered before this batch, exactly as design.md predicted.

## Remaining Tasks (out of scope for PR1)

- [ ] Phase 2: Port + Adapters + Slug (PR 2)
- [ ] Phase 3: API Routes (PR 3)
- [ ] Phase 4: Frontend (PR 4)
- [ ] Phase 5: Final Verification / Cleanup

## Status (PR1)

8/8 Phase 0 + Phase 1 tasks complete (2 prerequisite + 6 implementation).
Ready for `sdd-verify` on this PR1 slice, then PR2 (`sdd-apply` Phase 2)
targets this branch per `stacked-to-main`.
