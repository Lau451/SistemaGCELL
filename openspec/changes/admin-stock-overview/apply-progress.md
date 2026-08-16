# Apply Progress: Admin Stock Overview

Single apply batch — all 13 tasks (Phases 1-6) completed, backend + frontend, single PR.

## Status: DONE (13/13 tasks)

## Files Created

- `backend/src/gcell/stock/application/catalog_stock_levels_reader.py` — `CatalogStockLevelsReader(Protocol)`, a NEW sibling to `StockLevelReader` (not a widened Protocol), declaring exactly `async def quantities_for_variants(self, variant_ids: Sequence[UUID]) -> dict[UUID, int]`. Docstring documents the one-entry-per-requested-id totality contract.
- `backend/tests/unit/stock/test_catalog_stock_levels_reader_port.py` — port-shape test (`CatalogStockLevelsReader` public members == `{"quantities_for_variants"}`) plus 4 `InMemoryStockLevelReader.quantities_for_variants` behavior tests: empty input → `{}`, no-movement id → `0`, movements sum correctly, unrequested ids' movements excluded.

## Files Modified

- `backend/src/gcell/stock/infrastructure/in_memory_stock_level_reader.py` — added `quantities_for_variants(variant_ids)`: seeds `{vid: 0 for vid in variant_ids}`, then a single pass over `self._movements` overlays summed `quantity_delta` for requested ids only. `quantity_on_hand` (single-variant method) untouched.
- `backend/src/gcell/stock/infrastructure/postgres_stock_level_reader.py` — added `quantities_for_variants(variant_ids)`: empty input short-circuits to `{}` with zero round trips; otherwise one `SELECT variant_id, quantity_on_hand FROM variant_stock_levels WHERE variant_id = ANY($1::uuid[])`, dict seeded with `0` per requested id then overlaid with fetched rows (totality in Python, not SQL). `quantity_on_hand` (single-variant method) untouched.
- `backend/tests/integration/db/test_stock_movement_repository.py` — 4 new integration tests against real local Postgres (`db_conn`, reusing `make_persisted_variant_id`): bulk result matches each variant's `quantity_on_hand` with mixed restock/sale deltas; a zero-movement variant resolves to `0` (present key); a variant not in the requested id list is excluded even though it has movements; `quantities_for_variants([])` → `{}`.
- `backend/tests/integration/api/test_admin.py` — added `import asyncpg` and `PostgresStockLevelReader`/`CreateStockedProductUseCase` imports; updated `test_valid_token_with_pool_returns_200_with_product_rows` to give the fixture product one variant, spy `PostgresStockLevelReader.quantities_for_variants`, and assert the returned variant carries `quantity_on_hand`; added `test_list_admin_products_calls_bulk_stock_reader_exactly_once` (3 products x 2 variants → bulk reader called exactly once with all 6 ids, D3); added `test_list_admin_products_bulk_stock_read_failure_returns_500` (bulk-read raises `asyncpg.PostgresConnectionError` → 500, no partial/degraded 200 body, D6); added `test_get_admin_product_by_id_response_has_no_quantity_on_hand_key` and `test_create_admin_product_response_has_no_quantity_on_hand_key` (D7 — GET-by-id and POST responses never carry the new key).
- `backend/src/gcell/api/admin.py` — added `AdminProductListVariantResponse` (the existing four variant fields plus `quantity_on_hand: int`) and `AdminProductListItemResponse` (`from_domain(product, quantities)` classmethod) as genuinely separate models, NOT subclasses of `AdminProductVariantResponse`/`AdminProductResponse` (a subclass would silently drop the extra key on Pydantic serialization by declared type). Rewrote `list_admin_products` to acquire one connection, call `PostgresProductRepository(conn).list_all()`, then `PostgresStockLevelReader(conn).quantities_for_variants([...])` exactly once for every variant across every returned product, and build the response via `AdminProductListItemResponse.from_domain`. No `_execute_or_raise` wrapping (D6) — a bulk-read failure propagates naturally to FastAPI's default 500, identical to how a `list_all()` failure already behaves. `AdminProductResponse`, `get_admin_product`, `create_admin_product`, `update_admin_product` are byte-for-byte untouched (D7).
- `frontend/src/app/(admin)/admin/products/page.tsx` — `AdminProductVariant` gained `quantity_on_hand: number`. Each variant `<li>` now renders `{color} — {price} / {cost} — {quantity}`; when `quantity_on_hand === 0` the `<li>` carries the literal `text-destructive` class plus an "Out of stock" label — same class name and label text as `stock-manager.tsx:98-109`, no new convention.
- `frontend/src/app/(admin)/admin/products/page.test.tsx` — existing fixture variant extended with `quantity_on_hand: 12`. Added 3 new tests: non-zero quantity renders with no "Out of stock" label; zero quantity renders "Out of stock" whose containing `<li>` carries `text-destructive` (matching `stock-manager.test.tsx`'s `.closest()` assertion pattern); rendering stock issues no additional `fetch` call beyond the existing single `/api/admin/products` call.

## Test Results

- Backend focused (Phase 1-2, RED confirmed then GREEN): `pytest tests/unit/stock/test_catalog_stock_levels_reader_port.py` — RED: `ModuleNotFoundError` (Protocol file didn't exist yet); GREEN: 5 passed.
- Backend focused (Phase 1-2 regression): `pytest tests/unit/stock -v` — 50 passed, `test_stock_level_reader_port.py` (existing) unmodified and green.
- Backend focused (Phase 3, RED confirmed against real local Postgres via `npx supabase start` / `DB_URL`): `pytest tests/integration/db/test_stock_movement_repository.py` — RED: 4 failed (`AttributeError: no attribute 'quantities_for_variants'`), 8 passed (pre-existing); GREEN: 12 passed.
- Backend focused (Phase 4, RED confirmed): `pytest tests/integration/api/test_admin.py -k "product_rows or bulk_stock or quantity_on_hand"` — RED: 3 failed, 2 passed; GREEN (full file): 25 passed.
- Backend Phase 6.1: `pytest tests/unit/stock tests/integration/api tests/integration/db -v` — 181 passed.
- Backend full suite: `pytest -q` — 319 passed, 2 warnings (pre-existing, unrelated: Starlette/httpx deprecation + a Pillow `DecompressionBombWarning` in an existing image test).
- Backend Phase 6.3: `pytest -k domain_boundary` — 1 passed (`stock -> products` direction unchanged, no domain-layer framework imports).
- Frontend focused (Phase 5, RED confirmed): `npm test -- page.test.tsx` — RED: 3 failed, 13 passed; GREEN: 16 passed (4 files).
- Frontend full suite: `npm test` — 281 passed, 42 files (`stock-manager.test.tsx` and all product CRUD tests pass unmodified).
- `git diff --stat supabase/migrations/` — empty (zero diff, no migration).

## TDD Cycle Evidence

| Task | RED | GREEN | REFACTOR |
|---|---|---|---|
| 1.1/1.2 | `test_catalog_stock_levels_reader_port.py` (port-shape) failed with `ModuleNotFoundError` before `catalog_stock_levels_reader.py` existed | Protocol file created; port-shape test + all 50 `tests/unit/stock` pass | None needed |
| 2.1/2.2 | Same test file's 4 `InMemoryStockLevelReader.quantities_for_variants` cases failed (`AttributeError`, method absent) before the adapter change | `quantities_for_variants` added to `in_memory_stock_level_reader.py`; all 4 cases + full `tests/unit/stock` (50) pass | None needed |
| 3.1/3.2 | 4 new cases in `test_stock_movement_repository.py` failed against real local Postgres (`AttributeError`) before the adapter change; 8 pre-existing db tests stayed green throughout | `quantities_for_variants` added to `postgres_stock_level_reader.py`; all 12 db tests pass | None needed |
| 4.1/4.2 | 3 new/modified `test_admin.py` cases failed (`assert 0 == 1` call-count, `assert 200 == 500`, and the pre-change response missing `quantity_on_hand`) before the route/model change | Response models + `list_admin_products` rewrite land; all 25 `test_admin.py` cases pass | None needed |
| 5.1/5.2 | 3 new `page.test.tsx` cases failed (`getByText("3")` element not found, etc.) before the render change | `AdminProductVariant.quantity_on_hand` + zero-stock render branch added; all 16 `page.test.tsx` cases pass | None needed |

## Deviations From Design

None. Implementation matches design.md exactly: `CatalogStockLevelsReader` is a new sibling file (Decision 1); both existing adapter classes gained the method, no new adapter class; totality (`{vid: 0}` seed + overlay) lives in each adapter, not the route (Decision 2); `AdminProductListItemResponse`/`AdminProductListVariantResponse` are genuinely separate models, never a subclass, list-only (Decision 3); no `_execute_or_raise` wrapping on the bulk read (Decision 4); the frontend reuses `stock-manager.tsx`'s exact `text-destructive` class and "Out of stock" label (Decision 5). No Supabase migration, no domain file change, no new endpoint/route, no new frontend proxy route — all confirmed unchanged.

## Issues Found

None. One test-construction note: `test_list_admin_products_bulk_stock_read_failure_returns_500` uses `TestClient(app, raise_server_exceptions=False)` so the unhandled `asyncpg.PostgresConnectionError` surfaces as an actual HTTP 500 response instead of propagating as a Python exception through the test client — this is the standard FastAPI/Starlette testing idiom for asserting default-500 behavior, not a deviation from D6.
