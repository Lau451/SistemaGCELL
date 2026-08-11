# Tasks: Admin Product CRUD

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1400-1600 (design.md's own estimate) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 migration+read filters → PR2 port+adapters+slug → PR3 API routes → PR4 frontend |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Migration + read filters, no admin-facing behavior change | PR 1 | `cd backend && uv run pytest tests/integration/db/test_product_repository.py tests/integration/db/test_catalog_soft_delete_views.py -v` | N/A — no HTTP surface changes; verify via `npx supabase migration up` + raw SQL against local Postgres | Revert migration SQL file + `postgres_product_repository.py` SELECT diff; additive column, no data destroyed |
| 2 | Port + adapters + slug generator, no route wired yet | PR 2 | `cd backend && uv run pytest tests/unit/products/ tests/integration/db/test_product_repository.py -v` | N/A — no route calls these methods yet; unit + db-integration tests are the harness | Revert `slug.py`, `repository.py` port additions, both adapters' new methods, `create_product.py`/`update_product.py`/`retire_product.py`; PR1 stays valid standalone |
| 3 | API routes wired to PR2's use cases | PR 3 | `cd backend && uv run pytest tests/integration/api/test_admin.py -v` | `curl` against local `uvicorn` with a minted test admin token: POST/PATCH/DELETE per design.md's curl pattern | Revert new routes + Pydantic models in `admin.py`; PR1/PR2 stay valid standalone |
| 4 | Frontend relay, actions, forms, pages | PR 4 | `cd frontend && npm test -- backend-fetch api-error actions product-form catalog-route-conformance` | `npm run dev`; manual click-through create → edit → retire → confirm gone from `/admin/products` and public catalog | Revert new/modified frontend files; backend chain (PR1-3) stays valid standalone |

## Phase 0: Prerequisite (blocking, manual) — before PR1 apply

- [x] 0.1 Confirm the local Supabase stack is running (`npx supabase status`, or `db reset`) — the migration must apply before any backend read-filter change, otherwise every SELECT errors on an unknown column. DONE: confirmed via `npx supabase status` (core services — DB, Auth, REST, Studio — up; imgproxy/edge_runtime/pooler stopped, not needed).
- [x] 0.2 Pick the migration filename timestamp at apply time for `supabase/migrations/<timestamp>_products_soft_delete.sql`; it MUST sort after `20260810000502` (today's date, 2026-08-11, satisfies this trivially). No down-migration file — this repo has no `down` convention. DONE: `20260811000000_products_soft_delete.sql` (sorts after `20260810000502`, follows the existing `YYYYMMDDHHMMSS_snake_case.sql` convention).

## Phase 1: Migration + Read Filters (PR 1)

Spec coverage: product-catalog-schema (Soft-Delete Column, Views Exclude Soft-Deleted), admin-product-management (Zero Active Variants — the `ON`-vs-`WHERE` regression).

- [x] 1.1 Create `supabase/migrations/<timestamp>_products_soft_delete.sql`: `alter table products add column deleted_at timestamptz`; same on `product_variants`; `products_active_idx` and `product_variants_active_product_idx` partial indexes. DONE: `supabase/migrations/20260811000000_products_soft_delete.sql`; applied via `npx supabase migration up`, confirmed clean; columns/indexes verified against the real local Postgres via `asyncpg` (`deleted_at` on both tables, both partial indexes present with `WHERE (deleted_at IS NULL)`).
- [x] 1.2 Same migration: `create or replace view catalog_products` / `catalog_variants` / `catalog_product_images` — identical column lists, added `WHERE ... deleted_at is null` (cascade via `p.deleted_at is null` on the variants/images views, per design.md's exact SQL). DONE: same file; view column lists confirmed byte-identical to `frontend/src/lib/catalog/columns.ts` via `information_schema.columns` query against the applied views.
- [x] 1.3 RED `backend/tests/integration/db/test_product_repository.py` (extend): the `ON`-vs-`WHERE` trap — directly `UPDATE product_variants SET deleted_at = now()` via raw SQL (no port method exists yet) on every variant of one product, then assert `list_all()` still returns that product with `variants == []`. DONE: `test_list_all_keeps_product_with_every_variant_retired` — ran RED first (failed: retired variant still returned, proving the pre-fix adapter reads unfiltered rows), then GREEN after 1.4.
- [x] 1.4 GREEN `backend/src/gcell/products/infrastructure/postgres_product_repository.py`: add `deleted_at IS NULL` filters to `get_by_id`, `get_by_slug`, `list_all`; the variant join filter goes in `ON`, never `WHERE` — the single easiest way to break this change. DONE: `p.deleted_at IS NULL` added to each `WHERE` (product is the LEFT JOIN's driving side, safe in `WHERE`); `AND v.deleted_at IS NULL` added to every `LEFT JOIN ... ON` clause, never `WHERE`.
- [x] 1.5 RED `backend/tests/integration/db/test_catalog_soft_delete_views.py` (new): raw-SQL retire (direct `UPDATE`) of a product and, separately, of one variant on an otherwise-active product; assert `catalog_products`/`catalog_variants`/`catalog_product_images` exclude the retired rows (hero image included) and a live product is unaffected. DONE: 3 tests, all pass against the already-migrated views; RED proven separately by replaying the OLD (pre-migration) view definitions inside a rolled-back transaction and confirming the retired row leaked through — genuine before/after proof without a destructive down-migration.
- [x] 1.6 Regression: existing public-catalog tests (`columns.test.ts`, `queries.test.ts`) and any pre-existing backend catalog tests run unmodified and stay green. DONE: `npm test -- columns.test.ts queries.test.ts catalog-route-conformance.test.ts` → 30/30 passed, files unmodified; full backend suite 102/102 passed; full frontend suite 170/170 passed (no filter, both).

## Phase 2: Port + Adapters + Slug (PR 2)

Spec coverage: product-persistence (all 5 requirements), product-catalog-schema (Soft-Delete Never Touches `stock_movements`).

- [x] 2.1 RED `backend/tests/unit/products/test_slug.py`: table-driven `slugify` (per design.md's exact cases incl. 200-char truncation and the emoji-only `UnslugifiableProductNameError` case). DONE: 6 RED cases written first (`ModuleNotFoundError`, module didn't exist), confirmed failing before any production code.
- [x] 2.2 GREEN `backend/src/gcell/products/application/slug.py`: `slugify`. DONE: NFKD-normalize + combining-mark strip + lowercase + non-alnum-run-to-hyphen + 76-char truncation with `rstrip("-")`; all 6 table cases pass.
- [x] 2.3 RED same file: `generate_unique_slug` via `InMemoryProductRepository` — same name x3 → `base`/`base-2`/`base-3`; a **retired** product still reserves its slug (next is `base-2`); 100-attempt bound raises. DONE: 4 RED cases (required 2.6/2.7's Protocol + adapter methods to exist first — implemented those ahead of numeric order as a legitimate dependency, noted in Deviations).
- [x] 2.4 GREEN `slug.py`: `generate_unique_slug`. DONE: bounded 100-attempt probe loop via `repository.slug_exists`; `SlugGenerationExhaustedError` added locally in `slug.py` (not `exceptions.py` — a generation-specific concern, not a port-contract error).
- [x] 2.5 GREEN `backend/src/gcell/products/application/exceptions.py`: add `ProductNotFoundError`, `VariantNotFoundError`, `UnslugifiableProductNameError`. DONE: all 3 added; exercised transitively as RED by the use-case and adapter tests that reference them before they existed.
- [x] 2.6 GREEN `backend/src/gcell/products/application/repository.py`: add `update`, `soft_delete`, `soft_delete_variant`, `slug_exists` to the `ProductRepository` Protocol (exact signatures/docstrings from design.md). DONE: docstrings copied verbatim from design.md's "Port additions" block.
- [x] 2.7 GREEN `backend/src/gcell/products/infrastructure/in_memory_product_repository.py`: implement the 4 new methods; add a `_deleted: set[UUID]` mirror; `slug_exists` deliberately ignores it. DONE: `update` merges incoming variants by id into existing (never deletes); `soft_delete_variant` drops the variant from the list (in-memory has no per-variant retired-but-visible state, mirrors the read-time filter's net effect).
- [x] 2.8 RED `backend/tests/unit/products/test_create_product_use_case.py` (new): slug derivation + collision path via `create_product.py`, wrapping `RegisterProductUseCase`. DONE: 3 RED cases, confirmed failing (`ModuleNotFoundError`) before GREEN.
- [x] 2.9 GREEN `backend/src/gcell/products/application/create_product.py`. DONE: `generate_unique_slug` then delegates to `RegisterProductUseCase.execute` unmodified.
- [x] 2.10 RED `backend/tests/unit/products/test_update_product_use_case.py` (new): rename does NOT change `slug` (explicit assert); update on a retired id → `ProductNotFoundError`; variant of another product → `VariantNotFoundError`. DONE: 6 RED cases, confirmed failing before GREEN.
- [x] 2.11 GREEN `backend/src/gcell/products/application/update_product.py`. DONE: ownership check via `repository.list_all()` scan (a variant id owned by a DIFFERENT product raises `VariantNotFoundError`; an id owned by nobody is treated as new) — documented as a design clarification in Deviations, since design.md specified the port contract but not this exact use-case-level IDOR check mechanism.
- [x] 2.12 RED `backend/tests/unit/products/test_retire_product_use_case.py` (new): retiring the **last** variant succeeds without retiring the product (Q4); product retire cascades to variants; single-variant retire leaves product and siblings active. DONE: 5 RED cases, confirmed failing before GREEN.
- [x] 2.13 GREEN `backend/src/gcell/products/application/retire_product.py`. DONE: `RetireProductUseCase`/`RetireVariantUseCase`, thin delegations to `soft_delete`/`soft_delete_variant` — no "≥1 active variant" invariant anywhere, per Q4.
- [x] 2.14 RED `backend/tests/integration/db/test_product_repository.py` (extend): adapter `update` reconciles in one transaction (a mid-way constraint violation leaves nothing persisted); `slug_exists` is `True` for a retired slug; `ON CONFLICT` on variant upsert never clears `deleted_at`. DONE: 17 RED cases added (update x5, soft_delete x3, soft_delete_variant x3, slug_exists x3, upsert-never-resurrects x1, ledger-safety x2), confirmed failing (`AttributeError`) before GREEN. The mid-transaction-failure case needed a genuine DB-only constraint (`numeric(10,2)` overflow) since `ON CONFLICT DO UPDATE` silently absorbs a duplicate-id-within-one-call (unlike plain `INSERT`) — noted in Deviations.
- [x] 2.15 RED same file: ledger safety — retire a product whose variant has `stock_movements` rows; `count(*)` and `sum(quantity_delta)` on `stock_movements` unchanged (the headline success criterion; no `UPDATE`/`DELETE` issued against that table). DONE: 2 tests (product-level and variant-level retirement), both prove ledger row count/sum invariance.
- [x] 2.16 GREEN `backend/src/gcell/products/infrastructure/postgres_product_repository.py`: implement `update`, `soft_delete`, `soft_delete_variant`, `slug_exists` per design.md's exact SQL (product `UPDATE`, per-variant `INSERT ... ON CONFLICT (id) DO UPDATE`, never touching `deleted_at` in the `SET` list). DONE: all 4 methods implemented byte-consistent with design.md's SQL; `update`'s field-edit `UPDATE` checked for 0-rows-affected BEFORE touching any variant (atomic ProductNotFoundError with zero side effects).
- [x] 2.17 RED `backend/tests/integration/db/test_catalog_soft_delete_views.py` (extend, from Phase 1): re-run the same view assertions using the new `soft_delete`/`soft_delete_variant` port methods instead of raw SQL, confirming parity. DONE: 2 new parity tests added, both pass, confirming the port methods produce identical DB state to PR1's raw-SQL proof.

## Phase 3: API Routes (PR 3)

Spec coverage: admin-api-access (all scenarios).

- [x] 3.1 RED `backend/tests/integration/api/test_admin.py` (extend): no token on `POST`/`PATCH`/either `DELETE` → `401`, repository spy never called, `require_db_pool` never reached. DONE: `test_no_token_on_write_routes_returns_401_and_never_calls_repository`, parametrized over all 4 write routes; confirmed RED (404 route-not-found, since routes didn't exist) before GREEN.
- [x] 3.2 RED same file: valid token + no pool → `503` on each write route, repository not invoked. DONE: `test_valid_token_with_no_pool_returns_503_on_write_routes`, same 4-route parametrization.
- [x] 3.3 RED same file: `slug` in a `POST`/`PATCH` body → `422` (`extra="forbid"` proves it, not silent drop). DONE: `test_slug_in_write_body_is_rejected_with_422`, asserts repository spy never called either.
- [x] 3.4 RED same file: valid `POST` → `201` with a server-generated `slug` the client never sent. DONE: `test_valid_post_creates_product_with_server_generated_slug`.
- [x] 3.5 RED same file: `PATCH`/`DELETE` on an unknown or already-retired id → `404`. DONE: 3 tests (`test_patch_unknown_or_retired_product_returns_404`, `test_delete_product_unknown_or_retired_returns_404`, `test_delete_variant_unknown_or_retired_returns_404`).
- [x] 3.6 RED same file: IDOR across parents — `DELETE /admin/products/{A}/variants/{v_of_B}` → `404`, never `403` (never confirm cross-parent existence). DONE: `test_delete_variant_cross_parent_returns_404_not_403` — two REAL products created via `CreateProductUseCase` against the real local Postgres (`db_pool` fixture, not `db_conn`, to avoid an asyncpg-connection-across-event-loops conflict with `TestClient`'s own portal thread); confirmed RED (404 route-not-found before routes existed) then GREEN (genuine 404 `not_found`, variant B provably untouched afterward); explicit cleanup in `finally`.
- [x] 3.7 GREEN `backend/src/gcell/api/admin.py`: `AdminVariantInput`, `AdminProductWriteRequest` (`extra="forbid"`, `Decimal` price/cost — never a `float`), `AdminProductResponse`. DONE: byte-consistent with design.md's "Request models" block.
- [x] 3.8 GREEN `admin.py`: `POST /admin/products` → `CreateProductUseCase`, `201`. DONE.
- [x] 3.9 GREEN `admin.py`: `PATCH /admin/products/{id}` → `UpdateProductUseCase`, `200`. DONE.
- [x] 3.10 GREEN `admin.py`: `DELETE /admin/products/{id}` → `RetireProductUseCase`, `204`. DONE (task text said `soft_delete`; implemented via the PR2 use case per this PR's explicit constraint, never the repository method directly).
- [x] 3.11 GREEN `admin.py`: `DELETE /admin/products/{id}/variants/{variant_id}` → `RetireVariantUseCase`, `204`; `VariantNotFoundError` on cross-parent → `404`. DONE (task text said `soft_delete_variant`; same use-case-layer constraint as 3.10).
- [x] 3.12 GREEN `admin.py`: exception-to-status mapping per design.md's table (`422` domain `ValueError`/`TypeError`, `404` not-found, `409` `DuplicateProductSlugError`). DONE: single `_execute_or_raise` helper wraps every write route's use-case coroutine.
- [x] 3.13 Regression: `test_health.py`, `test_lifespan.py` run unmodified, stay green. DONE: both files run unmodified; confirmed green in isolation and as part of the full 160/160 suite.

## Phase 4: Frontend (PR 4)

Spec coverage: admin-product-management (forms/UI scenarios).
Note: ~550 lines estimated; if apply overruns, split into helper+actions / pages+form sub-PRs — flagged, not forced now.

- [x] 4.1 RED `frontend/src/lib/admin/__tests__/backend-fetch.test.ts`: stubbed `createSessionClient` + spied `fetch` — no claims → `unauthenticated`, `fetch` never called; relays method/body/`Bearer`; `204` → `body: null`; thrown fetch → `backend_unavailable`. DONE: 5 RED cases, confirmed failing (module not found) before GREEN.
- [x] 4.2 GREEN `frontend/src/lib/admin/backend-fetch.ts`: `adminBackendFetch`. DONE: gate via `getClaims()`, relay via `getSession().access_token`, `204` special-cased before `.json()`, `JSON.stringify(body)` verbatim (no numeric coercion).
- [x] 4.3 GREEN `frontend/src/app/api/admin/products/route.ts`: refactor onto `adminBackendFetch` (GET only, no POST); confirm the existing `route.test.ts` stays green unmodified. DONE: existing `route.test.ts` untouched, 4/4 still green — refactor invisible to it as designed.
- [x] 4.4 RED `frontend/src/app/api/admin/products/[id]/__tests__/route.test.ts` (new): GET-one proxy for the edit page. DONE: 4 RED cases, confirmed failing before GREEN.
- [x] 4.5 GREEN `frontend/src/app/api/admin/products/[id]/route.ts`. DONE: relays directly to a new backend `GET /admin/products/{id}` endpoint. Initially shipped as a list-and-filter workaround since `admin.py` had no such route (design.md listed one in its File Changes table, but it was missed from Phase 3's task breakdown) — orchestrator closed the gap post-PR3-merge by adding `GET /admin/products/{product_id}` to `admin.py` (reuses `get_by_id`, 2 new backend tests) and rewriting this route to relay directly, per user decision.
- [x] 4.6 RED `frontend/src/lib/admin/__tests__/api-error.test.ts`: `extractAdminError` — Pydantic list shape, string shape, unrecognized-body fallback. DONE: 6 RED cases, confirmed failing before GREEN.
- [x] 4.7 GREEN `frontend/src/lib/admin/api-error.ts`. DONE: normalizes both `detail` shapes; generic fallback for anything else.
- [x] 4.8 RED `frontend/src/app/(admin)/admin/products/actions.test.ts` (new): `adminBackendFetch` mocked — `201`→`revalidatePath`+`redirect`; `422`→returns `{error}`, no redirect; `unauthenticated`→redirect `/admin/login`; variant price/cost relayed as the exact submitted string, never parsed to a JS number (money-precision threat-matrix case). DONE: 11 RED cases, confirmed failing before GREEN, including the explicit money-precision test (`"0.10"` and `"1234.567"` proven to survive byte-for-byte as strings).
- [x] 4.9 GREEN `frontend/src/app/(admin)/admin/products/actions.ts`: `createProductAction`, `updateProductAction`, `retireProductAction`, `retireVariantAction`. DONE: all 4, all relay through `adminBackendFetch`; no `parseFloat`/`Number()` anywhere in the file.
- [x] 4.10 RED `frontend/src/app/(admin)/admin/products/product-form.test.tsx` (new): add a variant row; removing an **unsaved** row is client-only (no request); removing a **saved** row submits the retire action; error rendered with `role="alert"`. DONE: 6 RED cases, confirmed failing before GREEN.
- [x] 4.11 GREEN `frontend/src/app/(admin)/admin/products/product-form.tsx`: client component, `useState` rows, `useActionState`; no slug field, ever. DONE.
- [x] 4.12 GREEN `frontend/src/app/(admin)/admin/products/new/page.tsx`. DONE (no dedicated RED test per tasks.md's own granularity — thin wiring only, exercised transitively by `product-form.test.tsx`).
- [x] 4.13 RED+GREEN `frontend/src/app/(admin)/admin/products/[id]/page.tsx` (+ test): edit page, RSC fetch to `/api/admin/products/{id}`, no slug field exposed. DONE: 2 RED cases, confirmed failing before GREEN.
- [x] 4.14 GREEN `frontend/src/app/(admin)/admin/products/page.tsx` (modify): "New product" link, per-row Edit link + Retire form; update `page.test.tsx`. DONE: restructured to one row per PRODUCT (not per variant) — fixes a latent spec gap where a zero-variant product was previously unrenderable; 6/6 tests green.
- [x] 4.15 RED extend `frontend/src/lib/pwa/__tests__/catalog-route-conformance.test.ts`: `/admin/products/new`, `/admin/products/{id}`, `/api/admin/products/{id}` → `NetworkOnly`, zero source change to `runtime-caching.ts`. DONE: confirmed — the existing `isAdminOrMutatingRequest` prefix matchers already cover all 3 new paths; SHA256 pin on `runtime-caching.ts` unchanged, 12/12 green.
- [x] 4.16 Regression: `route.test.ts`, `columns.test.ts`, `queries.test.ts` and the pre-existing `catalog-route-conformance.test.ts` assertions run unmodified, stay green. DONE: full frontend suite 211/211 (was 170/170 baseline; +41 new, 0 regressions).

## Phase 5: Final Verification / Cleanup

- [x] 5.1 One documented manual E2E pass on the live local stack: create → edit → retire → confirm gone from `/admin/products` and the public catalog. DONE — orchestrator ran it directly against the live backend (port 8123) + local Supabase with the `e2e-admin@gcell.local` test user's real JWT: `POST /admin/products` (201, server-generated slug `e2e-funda-de-prueba-grande`) → confirmed visible in `catalog_products` via the public REST API → `PATCH` (renamed `name`/`model`, changed a variant) → confirmed slug unchanged in both the response and the public catalog row → `DELETE` (204) → confirmed `GET /admin/products/{id}` now `404`, product absent from `GET /admin/products`, and absent from `catalog_products`. Full chain verified. No Playwright exists in this repo (design.md's documented limitation).
- [x] 5.2 Confirm no restore/undo control exists anywhere in the admin UI (spec: No Restore Capability In This Change). DONE — independently re-verified by sdd-verify (static read of all admin/products files, zero matches) AND now covered by a runtime regression test (`page.test.tsx`: "never renders a restore control or a show-retired filter/toggle").
- [x] 5.3 Confirm no "show retired" filter/toggle exists on any admin list screen (spec: No Show-Retired Filter). DONE — same verification and same new runtime test as 5.2.
- [x] 5.4 Full regression: `npm --prefix frontend test && uv run --project backend pytest -q`, confirm all green. DONE — 212/212 frontend (211 + the new negative-assertion test), 163/163 backend (with `DB_URL` set), `npx tsc --noEmit` clean, `npm run build` succeeds with all routes registered.
- [x] 5.5 Document the final migration filename and the soft-delete behavior note in the relevant README if project convention requires it. N/A — checked both `backend/README.md` (empty) and `frontend/README.md` (unmodified `create-next-app` boilerplate): this project has no established README-as-documentation convention. New env vars go in `.env.example` (already correct, no new vars this change needed), and behavior/decision documentation lives in `openspec/` (design.md, specs/) — consistent with every prior archived change, none of which touched a README either.
