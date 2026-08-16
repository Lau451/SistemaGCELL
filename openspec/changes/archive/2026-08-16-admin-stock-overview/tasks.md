# Tasks: Admin Stock Overview

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~260-340 (backend ~200-260, frontend ~60-80) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

Rationale: no new use case, no domain change, no migration, no new endpoint —
one Protocol file (~15 lines), one method added to each of two already-tested
adapters (~20-25 lines each), two new list-only response models + a route
composition edit in `admin.py` (~50-60 lines), one new backend test file plus
extensions to two existing backend test files (~110-140 lines), and a frontend
interface field + render branch plus test extensions (~60-80 lines). Smaller
than `admin-initial-stock-seeding` (~380-430, Medium) because there is no
transactional write path, no use case, and no new frontend field/state.

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Backend bulk stock port + adapters + list route composition + frontend list render | PR 1 | `cd backend && uv run pytest tests/unit/stock/test_catalog_stock_levels_reader_port.py tests/integration/db/test_stock_movement_repository.py tests/integration/api/test_admin.py -v && cd frontend && npm test -- page.test.tsx` | Local Supabase Postgres (`db_conn` fixture, extends `test_stock_movement_repository.py`) | Revert `catalog_stock_levels_reader.py` + adapter method diffs + `admin.py` list-route/models diff + `page.tsx`/`page.test.tsx` diff; `GET /admin/products/{id}/stock` and every write route untouched |

## Phase 1: Backend — New port (D1, spec: Bulk Catalog-Wide Current-Stock Read)

- [x] 1.1 RED `backend/tests/unit/stock/test_catalog_stock_levels_reader_port.py` (new) — `CatalogStockLevelsReader` Protocol declares exactly `{quantities_for_variants}` (mirrors `test_stock_level_reader_port.py`); confirm existing `test_stock_level_reader_port.py` stays green unmodified (`StockLevelReader` untouched).
- [x] 1.2 GREEN `backend/src/gcell/stock/application/catalog_stock_levels_reader.py` (new) — `CatalogStockLevelsReader(Protocol)` with `async def quantities_for_variants(self, variant_ids: Sequence[UUID]) -> dict[UUID, int]`, docstring notes one-entry-per-requested-id totality (design Decision 2).

## Phase 2: Backend — In-memory adapter behavior (D2 totality, spec: variant with zero movements → 0)

- [x] 2.1 RED extend `backend/tests/unit/stock/test_catalog_stock_levels_reader_port.py` — `InMemoryStockLevelReader.quantities_for_variants`: `[]` → `{}`; an id with no recorded movements → `0`; an id with recorded movements → sum of `quantity_delta`; requesting a subset of ids excludes other variants' movements from the result.
- [x] 2.2 GREEN `backend/src/gcell/stock/infrastructure/in_memory_stock_level_reader.py` — add `quantities_for_variants(variant_ids)`: seed `{vid: 0 for vid in variant_ids}`, single pass over `self._movements` overlaying summed `quantity_delta` per requested id only.

## Phase 3: Backend — Postgres adapter (D3 single query, spec: exactly one query regardless of variant count)

- [x] 3.1 RED extend `backend/tests/integration/db/test_stock_movement_repository.py` (`db_conn`, reuse `make_persisted_variant_id`) — bulk result for two persisted variants equals each one's `quantity_on_hand` (mixed restock/sale deltas); a variant with no movements resolves to `0` in the dict, never a missing key; a variant not included in the requested id list is absent from the result even though it has movements; `quantities_for_variants([])` returns `{}`.
- [x] 3.2 GREEN `backend/src/gcell/stock/infrastructure/postgres_stock_level_reader.py` — add `quantities_for_variants(variant_ids)`: empty input short-circuits to `{}` with zero round trips; else one `SELECT variant_id, quantity_on_hand FROM variant_stock_levels WHERE variant_id = ANY($1::uuid[])` (note: `quantity_on_hand`, not `quantity`), seed `{vid: 0 for vid in variant_ids}` then overlay fetched rows (design Decision 2, Interfaces/Contracts SQL).

## Phase 4: Backend — Route composition + list-only response models (D3/D6/D7, spec: GET /admin/products response)

- [x] 4.1 RED extend `backend/tests/integration/api/test_admin.py` — update `test_valid_token_with_pool_returns_200_with_product_rows` to spy `PostgresStockLevelReader.quantities_for_variants` and assert each returned variant carries `quantity_on_hand`; add: reader called exactly once regardless of product/variant count (D3); bulk-read raising an exception → `500`, no partial/degraded body (D6, no `_execute_or_raise` involvement); `GET /admin/products/{id}` (singular) and `POST`/`PATCH /admin/products` responses are unchanged — no `quantity_on_hand` key present (D7).
- [x] 4.2 GREEN `backend/src/gcell/api/admin.py` — add `AdminProductListVariantResponse` (adds `quantity_on_hand: int` to the existing four fields) and `AdminProductListItemResponse` (`from_domain(product, quantities)` classmethod, list-only per D7); rewrite `list_admin_products` to acquire one connection, call `PostgresProductRepository(conn).list_all()` then `PostgresStockLevelReader(conn).quantities_for_variants([v.id for p in products for v in p.variants])` once, and build the response via `AdminProductListItemResponse.from_domain`; leave `AdminProductResponse`/`get_admin_product`/POST/PATCH untouched (D7).

## Phase 5: Frontend — List renders per-variant stock (D5 zero-stock reuse, spec: Admin Product List Displays Per-Variant Current Stock)

- [x] 5.1 RED extend `frontend/src/app/(admin)/admin/products/page.test.tsx` — fixture variants carry `quantity_on_hand`; a non-zero variant renders its quantity with no "Out of stock" label; a `0`-quantity variant renders "Out of stock" with the same `text-destructive` treatment as `stock-manager.tsx` (design Decision 5); no additional `fetch` call is issued to render stock (only the one existing `/api/admin/products` call).
- [x] 5.2 GREEN `frontend/src/app/(admin)/admin/products/page.tsx` — add `quantity_on_hand: number` to `AdminProductVariant`; render each variant's quantity and, when `quantity_on_hand === 0`, the literal `text-destructive` class plus "Out of stock" label (same class/label as `stock-manager.tsx:98-109`, no new convention).

## Phase 6: Verification

- [x] 6.1 `cd backend && uv run pytest tests/unit/stock tests/integration/api tests/integration/db -v` — full regression, confirm `test_stock_level_reader_port.py` (existing) and every write-route test pass unmodified.
- [x] 6.2 `cd frontend && npm test -- page.test.tsx` plus full `admin/products` suite — confirm `stock-manager.test.tsx` and product CRUD tests pass unmodified.
- [x] 6.3 Confirm `supabase/migrations/` has zero diff and `backend/tests/*domain_boundary*` still passes (no domain change, `stock → products` direction unchanged).
