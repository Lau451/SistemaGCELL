# Tasks: Admin Stock Movement History

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~950-1250 (backend ~550-620, frontend ~400-500) |
| 400-line budget risk | Medium — each work unit exceeds the 400-line per-PR guideline (as did the prior change's backend unit), and the combined total sits at/near the 1200-line session budget |
| Chained PRs recommended | Yes |
| Suggested split | PR1 (backend: port + use case + Postgres/in-memory adapters + route + tests) → PR2 (frontend: proxy + StockHistory component + page wiring + tests) |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

This change adds a NEW read-model DTO (`RecordedStockMovement`), a NEW port-shape proof test,
keyset-pagination logic (clamp + `limit+1` trim + cursor exclusivity across 2 pages), and a NEW
frontend component with its own client state (Decision 6) — more surface than
`admin-stock-management` (2 endpoints, no read-model DTO, no pagination), which landed at
~1150-1250 total. Split into the same 2 work units for the same reviewability reason: backend
(new port/use case/adapter, DB-level cursor correctness) and frontend (new stateful component,
allowlisted proxy passthrough) are independently reviewable, testable, and revertible.

### Suggested Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | `StockMovementHistoryReader` port + `RecordedStockMovement`, `ListVariantStockMovementsUseCase` + `StockMovementPage`, Postgres/in-memory adapters, GET route + 2 response models | PR 1 | `cd backend && uv run pytest tests/unit/stock/test_stock_movement_history_reader_port.py tests/unit/stock/test_list_variant_stock_movements.py tests/integration/stock/test_stock_movement_repository.py tests/integration/api/test_admin_stock.py -v` | Local Supabase Postgres (existing `require_db_pool` harness, same pattern as `test_stock_movement_repository.py`) | Revert new port/use case/adapter files + `admin.py` route/models diff; `stock/**` domain and write path untouched; no frontend dependents yet |
| 2 | GET proxy `movements/route.ts`, `stock-history.tsx` client component, wiring into `[id]/page.tsx` | PR 2 (base = PR 1 branch once merged, or main) | `cd frontend && npm test -- "movements/__tests__/route.test.ts" stock-history.test.tsx "[id]/page.test.tsx"` | `npm run dev` + local Supabase; manual "Load more" click-through on `/admin/products/[id]` | Revert new/modified frontend files; PR 1's endpoint stays valid standalone (pure additive, unused until this PR) |

## Phase A: Backend (PR 1, ~550-620 lines)

- [x] A.1 RED `backend/tests/unit/stock/test_stock_movement_history_reader_port.py`: `StockMovementHistoryReader` Protocol declares exactly `{list_for_variant}` (mirrors the two existing port-shape proofs; spec: stock-movement-recording "StockMovementRepository gains no new method" — proves the new port stays separate)
- [x] A.2 GREEN `backend/src/gcell/stock/application/stock_movement_history_reader.py`: `StockMovementHistoryReader` Protocol (`list_for_variant(variant_id, limit, before_id) -> list[RecordedStockMovement]`) + frozen `RecordedStockMovement` (`id`, `variant_id`, `movement_type`, `quantity_delta`, `reason`, `created_at`), reusing domain `MovementType` (design Decision 1)
- [x] A.3 RED `backend/tests/unit/stock/test_list_variant_stock_movements.py` + `backend/src/gcell/stock/infrastructure/in_memory_stock_movement_history_reader.py` (test double): unknown product → `ProductNotFoundError`, zero reader calls; foreign `variant_id` → `VariantNotFoundError`, zero reader calls; `limit=0` clamps to `1`, `limit=500` clamps to `100`, omitted `limit` defaults to `20`; use case requests `limit+1` and trims so `next_before_id` is `None` only at the true end; empty variant → `[]` with `next_before_id: None` (spec: stock-movement-recording "Cursor pagination…", "Limit above the hard cap is clamped…"; design Decision 3)
- [x] A.4 GREEN `backend/src/gcell/stock/application/list_variant_stock_movements.py`: `ListVariantStockMovementsUseCase(products, history_reader)` — resolve product, ownership-check `variant_id` (mirrors `RecordVariantStockMovementUseCase`), clamp `max(1, min(limit, 100))`, fetch `limit+1`, trim to `StockMovementPage(items, next_before_id)` frozen dataclass (design Decision 3, Interfaces/Contracts)
- [x] A.5 RED extend `backend/tests/integration/db/test_stock_movement_repository.py` (tasks.md said `tests/integration/stock/...` — that path does not exist; the real sibling file lives at `tests/integration/db/`, confirmed by reading it before starting): `list_for_variant` returns rows ordered `id DESC`; `before_id` cursor is strictly exclusive; fetching page 2 with page 1's cursor yields IDs strictly less than every page-1 ID with no duplicates or gaps; a second variant's movements never appear in the first variant's pages (spec: stock-movement-recording "History reflects recorded movements newest-first", "Cursor pagination returns strictly older rows…"; references not-yet-existing `PostgresStockMovementHistoryReader`)
- [x] A.6 GREEN `backend/src/gcell/stock/infrastructure/postgres_stock_movement_history_reader.py`: `PostgresStockMovementHistoryReader.list_for_variant` — keyset `SELECT id, variant_id, movement_type, quantity_delta, reason, created_at FROM stock_movements WHERE variant_id = $1 AND ($2::bigint IS NULL OR id < $2) ORDER BY id DESC LIMIT $3` (design Interfaces/Contracts)
- [x] A.7 RED extend `backend/tests/integration/api/test_admin_stock.py`: GET movements 401 with no JWT, spy proves zero `stock_movements` queries (spec: admin-stock-management "Movement history read without a JWT is rejected"); 404 for a `variant_id` belonging to another product, never 403 (spec: admin-api-access "Foreign variant_id returns 404, never 403"); 404 for an unknown `variant_id`; `200` with `items: []`, `next_before_id: null` for a zero-movement variant; `?limit=500` clamped to `100` not rejected; `?before_id=abc` → `422`, not `500`; response shape is `{items, next_before_id}`; second-page items via `next_before_id` all have `id` strictly less than the first page's oldest `id` (design Testing Strategy "Integration — api")
- [x] A.8 GREEN `backend/src/gcell/api/admin.py`: add `AdminStockMovementHistoryItemResponse`, `AdminStockMovementHistoryPageResponse` (no `ConfigDict`, per design Decision 4); add `GET /admin/products/{product_id}/variants/{variant_id}/stock/movements` (query params `limit`, `before_id`; delegates to `ListVariantStockMovementsUseCase`) under the existing `Depends(verify_admin_jwt)` router (spec: admin-api-access "Variant Stock Movement History Endpoint")
- [x] A.9 Verify existing `stock/**` write-path, current-stock-read, and unrelated admin suites pass unmodified — full backend suite run: 294/294 passed

## Phase B: Frontend (PR 2, ~400-500 lines)

- [x] B.1 RED `frontend/src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/__tests__/route.test.ts`: proxy mirrors the existing stock GET proxy for auth cookie passthrough and backend error (401/502) passthrough; only `limit` and `before_id` are forwarded into a freshly built `URLSearchParams` — an injected arbitrary query param is dropped, never appended to the outbound backend URL (design Decision 7)
- [x] B.2 GREEN `frontend/src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/route.ts`: GET proxy allowlisting `limit`/`before_id`, calling `GET /admin/products/{id}/variants/{variantId}/stock/movements`
- [x] B.3 RED `frontend/src/app/(admin)/admin/products/stock-history.test.tsx`: zero-movement variant renders an empty state, not an error (spec: admin-stock-management "A variant with no movements renders an empty state"); rows render newest-first; clicking "Load more" appends the next page below existing rows without resetting the list (spec: "Load more appends older movements without resetting the list"); "Load more" is not rendered once `next_before_id` is `null`; no computed running-balance column and no type/date filter controls are rendered (spec: "Admin Views Per-Variant Movement History" — MUST NOT clauses); local entries/cursor state resets to page one when the `initialHistory` prop reference changes (spec: "Recording a movement resets the history view to page one"; design Decision 6 compare-prop-during-render pattern)
- [x] B.4 GREEN `frontend/src/app/(admin)/admin/products/stock-history.tsx`: `StockHistory({ variantId, initialHistory })` — local `useState` for entries + cursor (design Decision 6), "Load more" fetches the proxy with `before_id`, compare-prop-during-render reset when `initialHistory` reference changes
- [x] B.5 RED extend `frontend/src/app/(admin)/admin/products/[id]/page.test.tsx`: `fetchAdminProductStockHistory` is called server-side for the first variant; `<StockHistory>` renders below `<StockManager>` with the fetched `initialHistory` prop
- [x] B.6 GREEN `frontend/src/app/(admin)/admin/products/[id]/page.tsx`: add `fetchAdminProductStockHistory(id, variantId)` and render `<StockHistory>` wired to `variants[0]` (design Open Questions: single-variant prefetch, consistent with proposal Q3)
- [x] B.7 Verify existing `stock-manager`, product CRUD, image, and admin-auth frontend suites pass unmodified
