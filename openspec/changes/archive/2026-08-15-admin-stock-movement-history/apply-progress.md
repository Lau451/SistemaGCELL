# Apply Progress: Admin Stock Movement History

## Batch 1 (this run) — Phase A: Backend (PR 1)

**Mode**: Strict TDD
**Scope**: Phase A only (A.1–A.9). Phase B (frontend) untouched — out of scope for this batch.

### Completed Tasks
- [x] A.1 RED `backend/tests/unit/stock/test_stock_movement_history_reader_port.py`
- [x] A.2 GREEN `backend/src/gcell/stock/application/stock_movement_history_reader.py`
- [x] A.3 RED `backend/tests/unit/stock/test_list_variant_stock_movements.py` + `backend/src/gcell/stock/infrastructure/in_memory_stock_movement_history_reader.py`
- [x] A.4 GREEN `backend/src/gcell/stock/application/list_variant_stock_movements.py`
- [x] A.5 RED extend `backend/tests/integration/db/test_stock_movement_repository.py` (tasks.md says `tests/integration/stock/...`; that path doesn't exist — the real sibling file is under `tests/integration/db/`, confirmed against the codebase before writing)
- [x] A.6 GREEN `backend/src/gcell/stock/infrastructure/postgres_stock_movement_history_reader.py`
- [x] A.7 RED extend `backend/tests/integration/api/test_admin_stock.py`
- [x] A.8 GREEN `backend/src/gcell/api/admin.py` (route + 2 response models)
- [x] A.9 Verify existing suites pass unmodified — full backend suite: 294/294 passed

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `backend/tests/unit/stock/test_stock_movement_history_reader_port.py` | Created | Port-shape proof: `StockMovementHistoryReader` declares exactly `{list_for_variant}` |
| `backend/src/gcell/stock/application/stock_movement_history_reader.py` | Created | `StockMovementHistoryReader` Protocol + frozen `RecordedStockMovement` read-model DTO (reuses domain `MovementType`) |
| `backend/tests/unit/stock/test_list_variant_stock_movements.py` | Created | Unit tests: IDOR guard (zero reader calls before ownership check), limit clamp table (0→1, 500→100, omitted→20), `limit+1` trim boundary (exact-limit vs over-limit), empty-variant page |
| `backend/src/gcell/stock/infrastructure/in_memory_stock_movement_history_reader.py` | Created | In-memory test double mirroring the Postgres adapter's keyset semantics (`id DESC`, exclusive `before_id`) |
| `backend/src/gcell/stock/application/list_variant_stock_movements.py` | Created | `ListVariantStockMovementsUseCase` — ownership guard (mirrors `RecordVariantStockMovementUseCase`), clamp, `limit+1` fetch/trim, `StockMovementPage(items, next_before_id)` |
| `backend/tests/integration/db/test_stock_movement_repository.py` | Modified | Extended with 3 new tests: newest-first ordering, strictly-exclusive `before_id` cursor pagination (no dupes/gaps), cross-variant isolation |
| `backend/src/gcell/stock/infrastructure/postgres_stock_movement_history_reader.py` | Created | `PostgresStockMovementHistoryReader.list_for_variant` — keyset `SELECT ... WHERE variant_id = $1 AND ($2::bigint IS NULL OR id < $2) ORDER BY id DESC LIMIT $3`, maps rows to `RecordedStockMovement` (converts `movement_type` text column back to `MovementType`) |
| `backend/tests/integration/api/test_admin_stock.py` | Modified | Added `get-movement-history` to the 401 parametrized route list; extended `_spy_all_adapters`; 6 new tests: foreign-variant 404, unknown-variant 404, empty page `{items: [], next_before_id: null}`, `?limit=500` clamp (not rejected), `?before_id=abc` → 422 (not 500), 2-page cursor pagination via the real endpoint |
| `backend/src/gcell/api/admin.py` | Modified | Added `AdminStockMovementHistoryItemResponse` + `AdminStockMovementHistoryPageResponse` (no `ConfigDict`, per design Decision 4) and `GET /admin/products/{product_id}/variants/{variant_id}/stock/movements` route, composing `PostgresProductRepository` + `PostgresStockMovementHistoryReader` through `ListVariantStockMovementsUseCase`, reusing the existing `_execute_or_raise` exception→status mapping (no new exception types needed — `ProductNotFoundError`/`VariantNotFoundError` already map to 404) |

### TDD Cycle Evidence
| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| A.1/A.2 | `test_stock_movement_history_reader_port.py` | Unit | N/A (new) | ✅ Written (ModuleNotFoundError confirmed) | ✅ Passed | ➖ Skipped: structural, one-member Protocol, single possible output | ➖ None needed |
| A.3/A.4 | `test_list_variant_stock_movements.py` | Unit | ✅ 47/47 (baseline, stock module + admin_stock) | ✅ Written (ModuleNotFoundError confirmed) | ✅ Passed | ✅ 8 cases (2 IDOR-guard, 3 limit-clamp parametrized, exact-limit boundary, over-limit boundary, empty-variant) | ➖ None needed |
| A.5/A.6 | `test_stock_movement_repository.py` (extended) | Integration (DB) | ✅ 5/5 pre-existing rows in that file, run before edit | ✅ Written (ModuleNotFoundError confirmed against real Postgres) | ✅ Passed (real local Supabase) | ✅ 3 cases (ordering, cursor exclusivity/no-gaps, cross-variant isolation) | ➖ None needed |
| A.7/A.8 | `test_admin_stock.py` (extended) | Integration (API) | ✅ 12/12 pre-existing rows in that file, run before edit | ✅ Written (7 failures confirmed: 401-route param, 3×404-shape mismatches, empty-page KeyError, limit-clamp KeyError, before_id 405-not-422, cursor-pagination KeyError) | ✅ Passed (19/19 in file) | ✅ 6 new scenarios covering every RED assertion | ➖ None needed (ruff-clean after one line-length fix in `admin.py`) |

### Work Unit Evidence
| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest tests/unit/stock/test_stock_movement_history_reader_port.py tests/unit/stock/test_list_variant_stock_movements.py tests/integration/db/test_stock_movement_repository.py tests/integration/api/test_admin_stock.py -v` → **33 passed** (1 port + 8 use-case + 8 repo-integration + 19 api-integration; nested duplicates in count are the pre-existing rows re-run inside the same files, actual net-new: 1+8+3+7=19 new test functions) |
| Runtime harness command/scenario and exact result | Local Supabase Postgres via `npx supabase start` (started fresh this session, was not running) + `require_db_pool`/`db_conn` harness — same pattern as the existing `test_stock_movement_repository.py`. Real DB round-trip exercised in `test_list_for_variant_paginates_with_strictly_exclusive_before_id_cursor` and the 2-page API test. All passed. |
| Rollback boundary | Revert 4 new files (`stock_movement_history_reader.py`, `list_variant_stock_movements.py`, `in_memory_stock_movement_history_reader.py`, `postgres_stock_movement_history_reader.py`) + the `admin.py` diff (new imports, 2 response models, 1 route — all additive, appended after the existing POST movement route) + the 2 extended test files' new test functions (also additive, appended after existing tests). No existing file's existing logic was altered. `stock/domain/**`, the write path, and the current-stock read are untouched. |

### Full Suite Confirmation
`cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest -q` → **294 passed, 2 warnings** (warnings are pre-existing: a `StarletteDeprecationWarning` about `httpx`/`starlette.testclient`, and a `DecompressionBombWarning` from an existing Pillow test — both unrelated to this change).

### Test Summary
- **Total tests written**: 19 new test functions (1 port-shape + 8 use-case unit + 3 DB integration + 7 API integration)
- **Total tests passing**: 19/19 new, 294/294 full suite
- **Layers used**: Unit (9), Integration-DB (3), Integration-API (7)
- **Approval tests** (refactoring): None — no refactoring tasks in this batch
- **Pure functions created**: 0 new pure functions (the clamp/trim logic lives inside `ListVariantStockMovementsUseCase.execute`, an async method with an I/O-bound reader call, so it isn't extracted as a standalone pure function — matches the precedent set by `RecordVariantStockMovementUseCase.execute`)

### Deviations from Design
None — implementation matches design.md exactly (Decision 1: separate `RecordedStockMovement` DTO; Decision 2: sibling Postgres adapter, not a method on `PostgresStockMovementRepository`; Decision 3: clamp in the use case + `limit+1` trim; Decision 4: no `ConfigDict` on response models). One path correction: tasks.md A.5 says `backend/tests/integration/stock/test_stock_movement_repository.py`, but the actual existing sibling file (read and confirmed before starting) is `backend/tests/integration/db/test_stock_movement_repository.py` — extended the real file, task description had a typo'd directory.

### Issues Found
None.

### Workload / PR Boundary
- Mode: chained/stacked PR slice (`stacked-to-main`, per session preflight)
- Current work unit: Unit 1 / PR 1 (backend) — matches tasks.md's Suggested Work Units table exactly
- Boundary: starts from a clean backend (no `stock_movement_history_reader.py` module existed) and ends with the GET movements endpoint fully wired, tested, and passing against real Postgres — Phase B (frontend proxy + component + page wiring) is untouched and will consume this endpoint in PR 2
- Estimated review budget impact: within the forecast's backend estimate (~550-620 lines); this is a self-contained, independently revertible PR 1

## Batch 2 (this run) — Phase B: Frontend (PR 2)

**Mode**: Strict TDD
**Scope**: Phase B only (B.1–B.7). Phase A (backend) already complete and merged to main (commits b84cadf, 6a4cc5e) — untouched this batch.

### Completed Tasks
- [x] B.1 RED `frontend/src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/__tests__/route.test.ts`
- [x] B.2 GREEN `frontend/src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/route.ts`
- [x] B.3 RED `frontend/src/app/(admin)/admin/products/stock-history.test.tsx`
- [x] B.4 GREEN `frontend/src/app/(admin)/admin/products/stock-history.tsx`
- [x] B.5 RED extend `frontend/src/app/(admin)/admin/products/[id]/page.test.tsx`
- [x] B.6 GREEN `frontend/src/app/(admin)/admin/products/[id]/page.tsx`
- [x] B.7 Verify existing frontend suites pass unmodified — full frontend suite: 272/272 passed (42 files)

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `frontend/src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/__tests__/route.test.ts` | Created | Proxy route tests: 401/502 passthrough, no-query relay, allowlisted `limit`/`before_id` forwarding with an injected arbitrary param dropped, 404 passthrough |
| `frontend/src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/route.ts` | Created | GET proxy — `adminBackendFetch` relay to `/admin/products/{id}/variants/{variantId}/stock/movements`; rebuilds `URLSearchParams` from an explicit allowlist (`limit`, `before_id`) rather than forwarding `request.url.search` verbatim (design Decision 7) |
| `frontend/src/app/(admin)/admin/products/stock-history.test.tsx` | Created | Component tests: empty state, newest-first row order, "Load more" append (asserts exact fetch URL/init), button hidden at `next_before_id: null`, no balance/filter controls rendered, compare-prop-during-render reset on new `initialHistory` reference |
| `frontend/src/app/(admin)/admin/products/stock-history.tsx` | Created | `StockHistory({ productId, variantId, initialHistory })` — local `useState` for `entries`/`cursor` (design Decision 6, deliberate deviation from `stock-manager.tsx`'s no-local-copy convention); "Load more" fetches the proxy with `before_id` and appends; compare-during-render reset (no `useEffect`) when the `initialHistory` object reference changes; uses shared `Button` component for style consistency with `stock-manager.tsx` |
| `frontend/src/app/(admin)/admin/products/[id]/page.test.tsx` | Modified | Extended the existing render test: added a 4th mocked fetch branch for the movements URL, assertions that `StockHistory` renders ("Movement history" heading + 1 list item) and that the 4th `fetch` call targets `/api/admin/products/p1/variants/v1/stock/movements` with the forwarded cookie header; fixed a test-data collision (`quantity_delta: 5` vs. `StockManager`'s `quantity_on_hand: 5`) by using `8` |
| `frontend/src/app/(admin)/admin/products/[id]/page.tsx` | Modified | Added `fetchAdminProductStockHistory(id, variantId)` (same cookie-forwarding self-fetch pattern as `fetchAdminProductStock`) and renders `<StockHistory>` below `<StockManager>`, wired to `product.variants[0]?.id` only — guarded with `EMPTY_STOCK_HISTORY` fallback for a variant-less product or a non-OK proxy response |

### TDD Cycle Evidence
| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| B.1/B.2 | `movements/__tests__/route.test.ts` | Unit (Route Handler) | N/A (new) | ✅ Written (module-not-found confirmed: `Failed to resolve import "../route"`) | ✅ Passed (5/5) | ✅ 5 cases (401, 502, no-query relay, allowlist-drop, 404 passthrough) — covers every RED assertion in one pass since each is a distinct branch | ➖ None needed |
| B.3/B.4 | `stock-history.test.tsx` | Unit (React component) | N/A (new) | ✅ Written (module-not-found confirmed: `Failed to resolve import "./stock-history"`) | ✅ Passed (6/6) | ✅ 6 cases (empty state, ordering, load-more append + exact fetch args, hidden-at-null, no-balance/filter, prop-reference reset) — covers every RED assertion in one pass | ✅ Clean — swapped a raw `<button>` for the shared `Button` component post-GREEN, ran tests again (still 6/6) to match `stock-manager.tsx`'s convention |
| B.5/B.6 | `[id]/page.test.tsx` (extended) | Unit (Server Component render) | ✅ 2/2 pre-existing rows in that file, run before edit | ✅ Written (failure confirmed: `getByText("Movement history")` — TestingLibraryElementError, element not found) | ✅ Passed (2/2 in file) after one test-data fix (quantity collision) | ➖ Skipped: single new server-fetch call with one deterministic response shape, no branching to triangulate beyond what B.1–B.4's own tests already cover | ➖ None needed |

### Work Unit Evidence
| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd frontend && npx vitest run "src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/__tests__/route.test.ts" "src/app/(admin)/admin/products/stock-history.test.tsx" "src/app/(admin)/admin/products/[id]/page.test.tsx"` → **13 passed** (5 route + 6 component + 2 page) |
| Runtime harness command/scenario and exact result | No local backend/DB runtime boundary in this PR — it consumes PR 1's already-merged, already-integration-tested endpoint through a thin proxy. The runtime-equivalent harness here is the jsdom-rendered Server/Client Component tree exercising real `fetch` calls (mocked at the network boundary only, per this codebase's established convention — same as `stock-manager.test.tsx` and `[id]/page.test.tsx`'s existing tests). `npm run dev` + manual click-through against local Supabase was NOT run this batch (no live backend session available in this environment); the proxy's URL-building and allowlist logic is fully covered by `route.test.ts`'s assertions on the exact outbound path, and PR 1's `test_admin_stock.py` already proves the real endpoint contract end-to-end. |
| Rollback boundary | Revert 4 new files (`movements/route.ts`, `movements/__tests__/route.test.ts`, `stock-history.tsx`, `stock-history.test.tsx`) + the `[id]/page.tsx`/`[id]/page.test.tsx` diffs (both additive: new import, new fetch fn, new prop-guarded render block; new test branch + 3 new assertions). No existing file's existing logic was altered. `stock-manager.tsx`, `product-form.tsx`, `image-manager.tsx`, and PR 1's backend are all untouched — PR 1's endpoint stays valid standalone regardless of this PR's fate. |

### Full Suite Confirmation
`cd frontend && npm test` (`vitest run`) → **272 passed** across **42 test files**, 0 failed.

Additional checks run (not part of the SDD test-command contract, but relevant static verification):
- `npx eslint` on all 6 new/modified Phase B files → 0 errors, 0 warnings
- `npx tsc --noEmit` (whole project) → 0 errors

### Deviations from Design
1. `StockHistory`'s prop signature is `{ productId, variantId, initialHistory }`, not the literal `{ variantId, initialHistory }` written in tasks.md B.4. `productId` is structurally required to build the proxy fetch URL (`/api/admin/products/{productId}/variants/{variantId}/stock/movements`) for both the "Load more" click and any future variant-switch fetch — the task's prop list reads as an abbreviation highlighting the two NEW/notable props (mirroring how `StockManager` also takes `productId` alongside its own notable `initialStock`), not an exhaustive contract. No design decision constrains this; Decision 5/6 discuss state ownership and reset semantics only, not the exact prop list.
2. `Load more` renders via the shared `Button` component (`@/components/ui/button`) rather than a raw `<button>` — matches `stock-manager.tsx`'s existing convention; not mentioned explicitly in design.md but consistent with its "match existing patterns" intent.
3. Everything else matches design.md exactly: Decision 5 (new sibling component, not an extension of `stock-manager.tsx`); Decision 6 (local `useState` for entries/cursor, compare-prop-during-render reset — implemented via a `trackedInitialHistory` state variable compared during render, no `useEffect`); Decision 7 (allowlisted `URLSearchParams` rebuild in the proxy, never `request.url.search` verbatim — proven by the "dropping an injected arbitrary query param" test); Open Questions (single-variant `variants[0]` server-side prefetch only).

### Issues Found
None. One pre-existing test-data collision was discovered and fixed during B.5 (RED confirmation) — the extended `page.test.tsx`'s new movement fixture used `quantity_delta: 5`, which collided with the pre-existing `StockManager` fixture's `quantity_on_hand: 5`, making `screen.getByText("5")` ambiguous. Changed the new fixture to `8`; not a production code issue.

### Workload / PR Boundary
- Mode: chained/stacked PR slice (`stacked-to-main`, per session preflight)
- Current work unit: Unit 2 / PR 2 (frontend) — matches tasks.md's Suggested Work Units table exactly
- Boundary: starts from PR 1's already-merged backend endpoint (consumed read-only, unmodified) and ends with the movement-history proxy, component, and page wiring fully implemented, tested, linted, and typechecked
- Estimated review budget impact: within the forecast's frontend estimate (~400-500 lines); this PR is a self-contained, independently revertible slice on top of `main` (PR 1 already merged)

### Status
16/16 tasks complete (Phase A + Phase B both done). Ready for `sdd-verify`.
