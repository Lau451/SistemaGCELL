# Tasks: Admin Stock Management

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1150-1250 (backend ~550-600, frontend ~600-650) |
| 400-line budget risk | Medium — combined estimate sits at/near the 1200-line session budget; each individual unit stays comfortably under it |
| Chained PRs recommended | Yes |
| Suggested split | PR1 (backend: use case + routes + tests) → PR2 (frontend: actions + proxy + UI + wiring) |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

File count alone (4 new + 2 modified, no migration, no new dependency) is materially smaller than
`admin-product-images` (7 slices, ~2880 lines) and `admin-product-crud` (4 slices, ~1400-1600
lines). The combined estimate could plausibly land in a single PR under the 1200 budget, but the
two-unit split is kept anyway for the same reviewability reason those two prior changes were
phased: backend (new trust boundary — IDOR guard, 2 routes, ~10 integration scenarios) and
frontend (new form + derived-sign logic + UI) are independently reviewable, independently
testable without the other, and independently revertible.

### Suggested Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | `RecordVariantStockMovementUseCase`, 2 admin routes, 3 Pydantic models, `UnknownVariantError` 404 mapping | PR 1 | `cd backend && uv run pytest tests/unit/stock/test_record_variant_stock_movement.py tests/integration/api/test_admin_stock.py -v` | Local Supabase Postgres (existing `require_db_pool` harness, same pattern as `test_admin_images.py`) | Revert new use-case file + `admin.py` routes/models/mapper diff; `stock/**` domain/infra/other application files untouched; no frontend dependents yet |
| 2 | `signedQuantityDelta`, `recordStockMovementAction`, GET stock proxy route, `StockManager` UI, wiring into `[id]/page.tsx` | PR 2 (base = PR 1 branch once merged, or main) | `cd frontend && npm test -- actions.test.ts stock-manager.test.tsx "stock/__tests__/route.test.ts" "[id]/page.test.tsx"` | `npm run dev` + local Supabase; manual record-movement click-through on `/admin/products/[id]` | Revert new/modified frontend files; PR 1's API surface stays valid standalone (pure additive, unused until this PR) |

## Phase A: Backend (PR 1, ~550-600 lines)

- [x] A.1 RED `backend/tests/unit/stock/test_record_variant_stock_movement.py`: unknown/retired product → `ProductNotFoundError`, spy proves zero `record` calls; `variant_id` owned by another product → `VariantNotFoundError`, zero `record` calls; soft-deleted variant (absent from `product.variants`) → `VariantNotFoundError`; happy path delegates `variant_id`/`movement_type`/`quantity_delta`/`reason` verbatim and returns the `StockMovement` (design.md Testing Strategy "Unit — use case"; spec: admin-stock-management "Movement Ownership Is Checked Before Any Write")
- [x] A.2 GREEN `backend/src/gcell/stock/application/record_variant_stock_movement.py`: `RecordVariantStockMovementUseCase(products, record_movement)` — resolve product, scan `product.variants` for `variant_id`, delegate to `record_movement.execute` (design.md Interfaces/Contracts, Decision 1)
- [x] A.3 RED extend `backend/tests/unit/api/test_admin.py` (or equivalent mapper test file): `_execute_or_raise` over an operation raising `UnknownVariantError` → `HTTPException(404, "not_found")` (design.md Testing Strategy "Unit — mapper", Decision 3; spec: admin-api-access "Unknown Variant Errors Map To 404")
- [x] A.4 GREEN `backend/src/gcell/api/admin.py`: add `UnknownVariantError` to the existing `except (ProductNotFoundError, VariantNotFoundError, ImageNotFoundError)` tuple → `404 "not_found"`
- [x] A.5 RED `backend/tests/integration/api/test_admin_stock.py` (mirrors `test_admin_images.py`): GET and POST 401 with a repository spy proving zero calls (spec: admin-stock-management "Stock Endpoints Require Admin Authorization"; admin-api-access "Stock Endpoints On The Admin Router"); GET 404 unknown product; GET returns `0` for a variant with no movements (spec: "A newly created variant reads zero stock"); POST 404 foreign `variant_id` (spec: "Movement for a variant of another product is rejected"); 422 for `sale` with `quantity_delta = +5` (spec: "Wrong-sign delta yields 422 with no write"); 422 unknown `movement_type` (spec: "Unknown movement type yields 422 with no write"); 422 `quantity_delta: 0`; 422 blank `reason`; 422 extra body field (`extra="forbid"`); adjustment with no `reason` succeeds (spec: "Adjustment without a reason succeeds"); 201-then-GET-readback `+10` restock, `-3` sale → `7` (spec: "Stock view reflects recorded movements") (design.md Testing Strategy "Integration — api")
- [x] A.6 GREEN `backend/src/gcell/api/admin.py`: add `AdminVariantStockResponse`, `AdminRecordStockMovementRequest` (`extra="forbid"`), `AdminStockMovementResponse` Pydantic models; add `GET /admin/products/{product_id}/stock` (loops `StockLevelReader.quantity_on_hand` per active variant, Decision 2) and `POST /admin/products/{product_id}/variants/{variant_id}/stock/movements` (calls `RecordVariantStockMovementUseCase.execute`, Decision 1), both under existing `Depends(verify_admin_jwt)` router (spec: admin-api-access "Stock Endpoints On The Admin Router")

## Phase B: Frontend (PR 2, ~600-650 lines)

- [x] B.1 RED `frontend/src/app/(admin)/admin/products/actions.test.ts`: `signedQuantityDelta` — restock/return → positive, sale/breakage → negative, adjustment honours `direction` (design.md Testing Strategy "Unit — frontend"; spec: admin-stock-management "Admin UI Derives Movement Sign From Type")
- [x] B.2 GREEN `frontend/src/app/(admin)/admin/products/actions.ts`: export `signedQuantityDelta(movementType, magnitude, direction)`
- [x] B.3 RED `actions.test.ts`: `recordStockMovementAction` builds the variant-scoped path (`.../variants/{id}/stock/movements`) and JSON body from `FormData`; omits blank `reason`; relays `quantity_delta` as a number; 201 → `revalidatePath(detail)` + `{error: null}`; non-201 → `extractAdminError`; unauthenticated → redirect to login (design.md Testing Strategy "Unit — frontend")
- [x] B.4 GREEN `actions.ts`: `recordStockMovementAction(productId, _prevState, formData)` using `adminBackendFetch`
- [x] B.5 RED `frontend/src/app/api/admin/products/[id]/stock/__tests__/route.test.ts`: GET proxy mirrors `[id]/images/route.ts` precedent (auth cookie passthrough, backend error passthrough)
- [x] B.6 GREEN `frontend/src/app/api/admin/products/[id]/stock/route.ts`: GET proxy calling `GET /admin/products/{id}/stock`
- [x] B.7 RED `frontend/src/app/(admin)/admin/products/stock-manager.test.tsx`: a `0`-quantity variant row renders the zero-stock highlight class, a non-zero row does not (spec: admin-stock-management "Zero-Stock Variants Are Visually Distinguished"); record form submits via `recordStockMovementAction.bind(null, productId)` with variant select + positive magnitude + `movement_type` (design.md Testing Strategy "Unit — frontend")
- [x] B.8 GREEN `frontend/src/app/(admin)/admin/products/stock-manager.tsx`: `StockManagerProps { productId, initialStock }`, table + single record form (Decisions 6, 7, 8)
- [x] B.9 GREEN wire into `frontend/src/app/(admin)/admin/products/[id]/page.tsx`: add `fetchAdminProductStock` and render `<StockManager>`; update `[id]/page.test.tsx` to cover the new fetch + render
- [x] B.10 Verify existing public-catalog, admin-auth, admin-CRUD, admin-image, and all `stock/` suites pass unmodified
