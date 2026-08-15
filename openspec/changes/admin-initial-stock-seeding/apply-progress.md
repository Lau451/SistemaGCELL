# Apply Progress: Admin Initial Stock Seeding

Single apply batch — all 14 tasks (Phases 1-4) completed, backend + frontend, single PR.

## Status: DONE (14/14 tasks)

## Files Created

- `backend/src/gcell/stock/application/create_stocked_product.py` — `CreateStockedProductUseCase(products, movements)`; mirrors `CreateProductUseCase`'s slug derivation, filters `initial_quantities` to `>0` entries, delegates to `RegisterStockedProductUseCase`.
- `backend/tests/unit/stock/test_create_stocked_product_use_case.py` — 6 unit tests: slug derivation, persistence, positive/zero/absent/mixed initial-quantity movement construction.
- `backend/tests/integration/api/test_admin_initial_stock.py` — 6 integration tests: 201+one restock movement, zero/absent quantity → zero movements, `-1` → 422 with zero repo calls, PATCH accepts+ignores the field, and a real-`db_pool` atomicity test (second seed failure rolls back product+variants+first movement).

## Files Modified

- `backend/src/gcell/api/admin.py` — `AdminVariantInput.initial_quantity: int = Field(default=0, ge=0)`; new `_to_seed_quantities` helper (zips `AdminVariantInput` items to server-generated `ProductVariant` ids); `create_admin_product` switched from `pool.acquire()` + `CreateProductUseCase` to `transaction(pool)` + `CreateStockedProductUseCase` (building `PostgresProductRepository` and `PostgresStockMovementRepository` on the SAME connection); removed now-unused `CreateProductUseCase` import; updated module + `_to_domain_variants` docstrings.
- `backend/tests/integration/api/test_admin.py` — added `transaction()` async-CM method to BOTH `_FakePool` classes in the file (Decision 3 fix), reusing the same `_FakeAcquireCtx` as `acquire()`. Purely additive — confirmed the two previously-passing tests (`test_valid_post_creates_product_with_server_generated_slug`, `test_post_with_unslugifiable_name_returns_422_not_500`) still pass.
- `frontend/src/app/(admin)/admin/products/product-form.tsx` — `VariantRow` gained `initialQuantity: string`; `addRow`/`toInitialRows` initialize it to `""`; `updateRow`'s field union widened; new "Initial quantity" `<input type="number" step="1" min="0" name="variant-initial-quantity">` rendered only when `row.id === null && productId === undefined` (Decision 4 gating — create mode only, never on the edit page even for a newly added row there).
- `frontend/src/app/(admin)/admin/products/actions.ts` — `VariantWritePayload` gained `initial_quantity?: string`; `buildVariantsPayload` reads `formData.getAll("variant-initial-quantity")`, zips positionally alongside color/price/cost, includes the key only when non-blank, relayed as a verbatim string (never `Number()`/`parseInt()`) — same convention as price/cost.
- `frontend/src/app/(admin)/admin/products/product-form.test.tsx` — 3 new tests: field renders in create mode, absent for existing (saved) rows, absent for a new row added on the edit page.
- `frontend/src/app/(admin)/admin/products/actions.test.ts` — 3 new tests: verbatim-string relay when non-blank, omitted when blank, omitted when the form field is absent entirely (edit-form shape).

## TDD Sequencing (Decision 3 constraint honored)

Task 2.1 (`_FakePool.transaction()`) landed in the SAME batch as, and before running, task 2.3 (route's `pool.acquire()` → `transaction(pool)` switch) — exactly as tasks.md's Phase 2 heading required ("sequence 2.1-2.3 together"). Verified: `test_valid_post_creates_product_with_server_generated_slug` and `test_post_with_unslugifiable_name_returns_422_not_500` both pass after the route change, confirming the fake-pool fix landed correctly and no `AttributeError`-driven 500 was introduced.

## Test Results

- Backend focused: `pytest tests/unit/stock/test_create_stocked_product_use_case.py tests/integration/api/test_admin_initial_stock.py tests/integration/api/test_admin.py` — all green throughout RED/GREEN cycles.
- Backend Phase 4.1: `pytest tests/unit/stock tests/integration/api` — 112 passed.
- Backend full suite: `pytest` — 306 passed, 2 warnings (pre-existing, unrelated: DeprecationWarning + a Pillow DecompressionBombWarning in an existing image test).
- Backend Phase 4.3: `pytest tests/architecture/test_domain_boundary.py` — 1 passed (stock -> products direction unchanged).
- Frontend focused: `npm test -- --run actions.test.ts product-form.test.tsx` — 53 passed.
- Frontend full suite: `npm test -- --run` — 278 passed, 42 files. One transient failure in `stock-manager.test.tsx` (untouched by this change) on the first combined run — reproduced as flaky: passed in isolation and on a full-suite re-run.

## Deviations From Design

None material. `_to_seed_quantities` uses `zip(..., strict=True)` (not explicitly specified in design.md's interface section) to fail loudly on any future accidental length mismatch between `AdminVariantInput` items and the `ProductVariant`s `_to_domain_variants` derives from them — both lists are always built from the same source list at the same call site, so this is defense-in-depth, not a behavior change. The 2.4 atomicity test simulates the DB-only failure mode (`UnknownVariantError`, raised for real by `PostgresStockMovementRepository.record` on an FK violation) via monkeypatch on the second `record()` call, since a real FK violation cannot be forced through the public request body (every variant id is server-generated) — same class of test-construction judgment call as `test_delete_variant_cross_parent_returns_404_not_403`'s own docstring justifies.
