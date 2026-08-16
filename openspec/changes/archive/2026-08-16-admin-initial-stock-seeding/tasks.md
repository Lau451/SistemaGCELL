# Tasks: Admin Initial Stock Seeding

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~380-430 |
| 400-line budget risk | Medium |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Medium

Rationale: reuses already-tested `RegisterStockedProductUseCase`; no new domain code; touches one existing route. Smaller than prior changes (~1150-1250, ~950-1250 lines) but sits close to the 400 budget — flag for the user rather than assume.

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Backend: seed-quantity use case + route wiring + atomicity | PR 1 | `pytest backend/tests/unit/stock/test_create_stocked_product_use_case.py backend/tests/integration/api/test_admin_initial_stock.py backend/tests/integration/api/test_admin.py` | Real `db_pool` rollback test (2.5) — genuinely new failure mode | Revert `create_stocked_product.py` + admin.py route diff; route falls back to `CreateProductUseCase` |
| 2 | Frontend: create-only initial-quantity field + payload relay | PR 1 | `vitest run product-form.test.tsx actions.test.ts` | N/A — pure component/unit tests, no live seed flow to exercise | Revert `product-form.tsx`/`actions.ts` diff; field/key disappears |

## Phase 1: Backend — CreateStockedProductUseCase (Decisions 1-2)

- [x] 1.1 RED: `backend/tests/unit/stock/test_create_stocked_product_use_case.py` (new) — slug derivation delegates through `RegisterStockedProductUseCase`; a variant with `initial_quantities[id] > 0` produces exactly one `restock` `StockMovement`; `0`/absent produces none; mixed variants only seed the `>0` ones.
- [x] 1.2 GREEN: `backend/src/gcell/stock/application/create_stocked_product.py` (new) — `CreateStockedProductUseCase(products, movements)`, `execute(name, model, variants, initial_quantities: Mapping[UUID,int] | None = None)`, mirrors `CreateProductUseCase` (slug + `Product(...)`), filters `>0`, delegates to `RegisterStockedProductUseCase`.

## Phase 2: Backend — Route wiring + regression-safe fake (Decision 3, sequence 2.1-2.3 together)

- [x] 2.1 `backend/tests/integration/api/test_admin.py` — add `transaction()` async-CM method to `_FakePool` (additive, same conn as `acquire()`). Required before 2.3 or `test_valid_post_creates_product_with_server_generated_slug` / `test_post_with_unslugifiable_name_returns_422_not_500` break.
- [x] 2.2 RED: `backend/tests/integration/api/test_admin_initial_stock.py` (new) — POST `initial_quantity: 5` -> 201 + `record()` called once; `0`/absent -> zero calls; `-1` -> 422, zero repo calls; PATCH accepts+ignores field.
- [x] 2.3 GREEN: `backend/src/gcell/api/admin.py` — add `initial_quantity: int = Field(default=0, ge=0)` to `AdminVariantInput`; add `_to_seed_quantities` helper (filters `>0`); switch `create_admin_product` to `transaction(pool)` building `PostgresProductRepository` + `PostgresStockMovementRepository` on the shared conn, call `CreateStockedProductUseCase`. Re-run 2.2 + full `test_admin.py` (Decision 3 regression check).
- [x] 2.4 RED: `test_admin_initial_stock.py` — real-`db_pool` test: 2 seeded variants, `record()` raises on 2nd call -> zero product/variant rows persisted (precedent: `test_delete_variant_cross_parent_returns_404_not_403`).
- [x] 2.5 GREEN: confirm 2.3's `transaction(pool)` scope already rolls back on the 2.4 failure; fix error propagation in `admin.py` only if it doesn't. (Confirmed no fix needed — the existing `transaction(pool)` scope already rolls back cleanly.)

## Phase 3: Frontend — Create-only initial-quantity field (Decision 4)

- [x] 3.1 RED: `product-form.test.tsx` — "Initial quantity" input renders only when `row.id === null && productId === undefined`; absent for existing rows and for new rows on the edit page.
- [x] 3.2 GREEN: `product-form.tsx` — render the gated input, wire to a `variant-initial-quantity` per-row state array.
- [x] 3.3 RED: `actions.test.ts` — `buildVariantsPayload` includes `initial_quantity` (string) when non-blank, omits the key when blank.
- [x] 3.4 GREEN: `actions.ts` — add `initial_quantity?: string` to `VariantWritePayload`; relay verbatim as a string (never `Number()`), matching the money-field convention.

## Phase 4: Verification

- [x] 4.1 `pytest backend/tests/unit/stock backend/tests/integration/api` — full regression. (112 passed; full suite: 306 passed)
- [x] 4.2 `vitest run` on `frontend/src/app/(admin)/admin/products` — full regression. (53 passed; full suite: 278 passed)
- [x] 4.3 Confirm `test_domain_boundary.py` still passes (`stock -> products` direction unchanged). (1 passed)
