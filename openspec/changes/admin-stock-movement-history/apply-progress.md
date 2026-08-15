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

## Batch 2 (pending) — Phase B: Frontend (PR 2)

- [ ] B.1 RED `frontend/.../movements/__tests__/route.test.ts`
- [ ] B.2 GREEN `frontend/.../movements/route.ts`
- [ ] B.3 RED `frontend/.../stock-history.test.tsx`
- [ ] B.4 GREEN `frontend/.../stock-history.tsx`
- [ ] B.5 RED extend `frontend/.../[id]/page.test.tsx`
- [ ] B.6 GREEN `frontend/.../[id]/page.tsx`
- [ ] B.7 Verify existing frontend suites pass unmodified

### Status
9/16 tasks complete (Phase A fully done). Ready for next batch (sdd-apply for Phase B) or sdd-verify on Phase A alone if PR 1 is verified/shipped independently per the stacked-PR chain strategy.
