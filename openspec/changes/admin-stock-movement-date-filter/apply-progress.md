# Apply Progress: Admin Stock Movement Date Filter

## Batch 1 (this run) — Phase 1-4: Backend (PR 1)

**Mode**: Strict TDD (RED → GREEN per phase, confirmed with real test runs — see TDD
Cycle Evidence below).
**Scope**: Phase 1 (exceptions + port) + Phase 2 (use case) + Phase 3 (both readers) +
Phase 4 (API wiring) only — tasks 1.1, 1.2, 2.1, 2.2, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3.
This is `tasks.md`'s Unit 1 / PR 1 (backend). Phase 5-11 (frontend date-filter UI,
frontend variant switcher, cleanup/final verification) are untouched — out of scope
for this batch, deferred to later apply runs once PR 1 merges (feature-branch-chain,
per `tasks.md`'s `Suggested Work Units` table).

**Retry note**: this batch was previously attempted and aborted mid-run due to an
API session-limit infrastructure error with zero code written (`tasks.md` had no
checkboxes marked). This run is a fresh, complete first attempt — no prior partial
state existed to merge.

### Completed Tasks
- [x] 1.1 `InvertedDateRangeError(ValueError)` — `backend/src/gcell/stock/application/exceptions.py`
- [x] 1.2 `since`/`until` on the `StockMovementHistoryReader` protocol — `stock_movement_history_reader.py`
- [x] 2.1 RED extend `tests/unit/stock/test_list_variant_stock_movements.py`
- [x] 2.2 GREEN `list_variant_stock_movements.py` (tz-normalize, midnight expansion, inverted-range raise)
- [x] 3.1 RED — `_SpyingHistoryReader`/`InMemoryStockMovementHistoryReader` extended (feeds 2.1)
- [x] 3.2 GREEN `in_memory_stock_movement_history_reader.py`
- [x] 3.3 RED extend `tests/integration/db/test_stock_movement_repository.py`
- [x] 3.4 GREEN `postgres_stock_movement_history_reader.py` (`$4`/`$5` predicates, `$3` stays `limit`)
- [x] 4.1 RED extend `tests/integration/api/test_admin_stock.py`
- [x] 4.2 GREEN `admin.py` route (two optional `datetime` params, no `Query()`, no new `except` arm)
- [x] 4.3 Confirmed `specs/admin-stock-management/spec.md` and `specs/admin-api-access/spec.md`
      deltas match shipped behavior — D4 (no-balance clause) and D5 (movement-type
      MUST NOT) are carried verbatim, unchanged, in both delta files

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `backend/src/gcell/stock/application/exceptions.py` | Modified | Added `InvertedDateRangeError(ValueError)`, constructor takes `since`/`until`, message `"since (...) is after until (...)"` via `.isoformat()`. A `ValueError` subclass so the existing `_execute_or_raise` `except (ValueError, ...)` branch in `admin.py` catches it with zero new code there (design D10) |
| `backend/src/gcell/stock/application/stock_movement_history_reader.py` | Modified | `StockMovementHistoryReader.list_for_variant` gains `since: datetime \| None = None, until: datetime \| None = None` |
| `backend/src/gcell/stock/application/list_variant_stock_movements.py` | Modified | `execute()` gains `since`/`until` params. Ownership guard (product/variant existence) still runs FIRST, unchanged. Then `_normalize_since`/`_normalize_until`: naive (`tzinfo is None`) values are stamped UTC; a naive `until` landing at exactly `00:00:00.000000` is further expanded to `+1 day − 1 microsecond` (D11, applies at the API boundary too, not only client-side). Then the inverted-range check (`since > until` after normalization) raises `InvertedDateRangeError`. Only then is `history_reader.list_for_variant` called, now passed the normalized `since`/`until` as two extra positional args |
| `backend/src/gcell/stock/infrastructure/in_memory_stock_movement_history_reader.py` | Modified | `list_for_variant` gains `since`/`until` (both defaulted `None`), filters `m.created_at >= since` / `m.created_at <= until` — inclusive both ends, matching the SQL predicate below |
| `backend/src/gcell/stock/infrastructure/postgres_stock_movement_history_reader.py` | Modified | SQL gains `AND ($4::timestamptz IS NULL OR created_at >= $4) AND ($5::timestamptz IS NULL OR created_at <= $5)`; `$3` stays `limit`, unchanged. `fetch()` call appends `since, until` as two new positional args after `limit` |
| `backend/src/gcell/api/admin.py` | Modified | `GET .../stock/movements` route gains `since: datetime \| None = None, until: datetime \| None = None` — plain typed params, no `Query(...)` validators. Passed straight through to `use_case.execute(..., since=since, until=until)`. No new `except` arm added to `_execute_or_raise` — its existing `ValueError` branch already covers `InvertedDateRangeError` |
| `backend/tests/unit/stock/test_list_variant_stock_movements.py` | Modified | `_SpyingHistoryReader.list_for_variant` signature widened to `(variant_id, limit, before_id, since=None, until=None)`; existing `reader.calls` assertions updated to 5-tuples. 6 new tests (see TDD Evidence) |
| `backend/tests/integration/db/test_stock_movement_repository.py` | Modified | New `insert_movement_at(conn, variant_id, created_at, quantity_delta=1)` helper — direct SQL `INSERT` bypassing `PostgresStockMovementRepository.record` (which never accepts `created_at`, DB-assigned via `default now()`); the append-only trigger only rejects `UPDATE`/`DELETE`, so an explicit `INSERT` value is unaffected. 3 new tests (see TDD Evidence) |
| `backend/tests/integration/api/test_admin_stock.py` | Modified | 3 pre-existing `fake_list_for_variant` monkeypatch stubs widened to accept `since=None, until=None` kwargs (the use case now always calls with 5 args). 5 new tests (see TDD Evidence) |

### TDD Cycle Evidence
| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1/2.2 | `test_list_variant_stock_movements.py` | Unit | ✅ 2/14 pre-existing tests unaffected by the tuple-shape change, run before edit | ✅ Written and confirmed: `uv run pytest tests/unit/stock/test_list_variant_stock_movements.py -q` → **12 failed, 2 passed** (`TypeError: ListVariantStockMovementsUseCase.execute() got an unexpected keyword argument 'since'` for the 6 new tests, plus 6 pre-existing tests failing on the now-5-tuple `reader.calls` assertion) | ✅ Passed: same command → **14 passed** after implementing `_normalize_since`/`_normalize_until`/the inverted-range raise and widening `_SpyingHistoryReader` | ✅ 6 new cases: naive→UTC normalize (non-midnight `until`, no expansion), naive-midnight `until` expands to `23:59:59.999999`, `since == until` valid (returns normally, not inverted), `since > until` raises `InvertedDateRangeError` with zero reader calls, ownership guard precedes the inverted-range check (foreign variant + inverted range → `VariantNotFoundError`, zero reader calls — proves ordering), omitting both reproduces the exact 5-tuple call shape `(variant_id, 21, None, None, None)` | ➖ None needed |
| 3.1-3.4 | `test_stock_movement_repository.py` | Integration (DB, real local Postgres) | ✅ 12/15 pre-existing tests unaffected, run before edit | ✅ Written and confirmed: `DB_URL=... uv run pytest tests/integration/db/test_stock_movement_repository.py -q` → **3 failed, 12 passed** (`TypeError: PostgresStockMovementHistoryReader.list_for_variant() got an unexpected keyword argument 'since'`) | ✅ Passed: same command → **15 passed** after adding the `$4`/`$5` SQL predicates | ✅ 3 new cases: rows exactly AT `since`/`until` are included (inclusive both ends, boundary rows via direct-SQL-inserted `created_at`), the range predicate composes with the existing `before_id` keyset predicate gap-free/duplicate-free across 3 pages of a 5-row filtered set, filtering stays scoped to the requested `variant_id` (no cross-variant leakage) | ➖ None needed |
| 4.1-4.3 | `test_admin_stock.py` | Integration (API, `TestClient` + monkeypatched adapters) | ✅ 29/32 pre-existing tests unaffected, run before edit | ✅ Written and confirmed: `DB_URL=... uv run pytest tests/integration/api/test_admin_stock.py -q` → **3 failed, 29 passed** (`since`/`until` silently dropped as undeclared query params by FastAPI — one test hit the real `PostgresStockMovementHistoryReader` against a dummy fake connection object, `AttributeError: 'object' object has no attribute 'fetch'`; two others failed because the route never forwarded `since`/`until`) | ✅ Passed: same command → **32 passed** after adding the two route params | ✅ 5 new cases: `?since`/`?until` reach the use case as normalized UTC `datetime`s; inverted range → `422` with body exactly `{"detail": str(InvertedDateRangeError(since, until))}`; `?since=not-a-date` → `422` via FastAPI's own type coercion, not `500`; omitting both params reproduces the exact pre-existing 200 response and calls the reader with `(None, None)`; a foreign `variant_id` combined with an inverted range on the same request still returns `404` (ownership guard wins, proving the same ordering at the HTTP layer) | ➖ None needed |

### Work Unit Evidence
| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest tests/unit/stock/test_list_variant_stock_movements.py tests/integration/db/test_stock_movement_repository.py tests/integration/api/test_admin_stock.py -v` → **61 passed** (14 unit + 15 DB integration + 32 API integration) |
| Runtime harness command/scenario and exact result | Local Supabase Postgres (`require_db_pool` harness) — confirmed running via `docker ps` (`supabase_db_SistemaGCELL` on `54322`) before any DB-backed test ran. `tests/integration/db/test_stock_movement_repository.py`'s 3 new tests exercise the real `stock_movements` table end-to-end (real `timestamptz` comparisons, real keyset pagination composed with the new range predicate) — genuine runtime proof, not a mock |
| Rollback boundary | Revert `exceptions.py`, `list_variant_stock_movements.py`, `stock_movement_history_reader.py`, both reader adapters, and the `admin.py` route diff (all additive — new optional params, one new predicate pair, one new exception class). Both `since`/`until` are optional (D7): reverting restores byte-identical prior behavior, confirmed by the "omitting both params reproduces the exact current response" test passing against the new code. Test-file diffs (3 files) revert alongside with zero impact on any other route or use case in the repo |

### Full Suite Confirmation
`cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest -q`
→ **352 passed, 2 warnings** (warnings are pre-existing and unrelated: a
`StarletteDeprecationWarning` about `httpx`/`starlette.testclient`, and a
`DecompressionBombWarning` from an existing Pillow test).

`uv run ruff check src/gcell/stock src/gcell/api/admin.py` → clean, no violations.

`uv run ruff format --check` on the 3 modified test files surfaced pre-existing
formatting drift on lines this batch never touched (verified via `git stash` +
re-run against the unmodified baseline — identical reformat diffs appear with zero
of this batch's changes applied). Not introduced by this batch; left as-is.

### Test Summary
- **Total tests written this batch**: 14 new test functions (6 unit + 3 DB integration + 5 API integration)
- **Total tests passing**: 14/14 new, 352/352 full backend suite
- **Layers used**: Unit (use case), Integration-DB (real Postgres, real `timestamptz`), Integration-API (`TestClient` + monkeypatched adapters)
- **Approval tests** (refactoring): None — no refactoring tasks in this batch
- **Pure functions created**: 2 new module-level pure functions — `_normalize_since`, `_normalize_until` in `list_variant_stock_movements.py` (tz-normalization + midnight expansion), kept separate from the async `execute()` method so the normalization rules are independently readable

### Deviations from Design
None — implementation matches design.md's DD1 (naive-datetime normalization and
midnight-`until` expansion happen server-side, application code, mirroring the
`limit` clamp precedent), D10 (inverted range → 422 via the existing `ValueError`
branch, zero new `except` arms), D11 (`until` inclusive of the whole day, both at
the API boundary for a naive midnight value and structurally via the `<=` SQL
predicate), and the exact File Changes / Interfaces-Contracts / Testing Strategy
tables byte-for-byte.

### Issues Found
None. The pre-existing `fake_list_for_variant` monkeypatch stubs in
`test_admin_stock.py` and the `_SpyingHistoryReader` in the unit test file both
needed their signatures widened to accept the two new `since`/`until` kwargs (with
`None` defaults) — an expected, mechanical consequence of extending the
`StockMovementHistoryReader` port shape, not a design gap.

### Workload / PR Boundary
- Mode: chained PR slice (feature-branch-chain, per `tasks.md`'s confirmed delivery
  decision; PR 1 of 3 — backend, then frontend date-filter UI, then frontend variant
  switcher)
- Current work unit: Unit 1 / PR 1 (backend: exceptions, port, use case, both
  readers, API wiring, both backend-relevant spec deltas)
- Boundary: starts from the pre-existing unfiltered movement-history endpoint (no
  `since`/`until` anywhere in the stack) and ends with the endpoint accepting both
  optional params, validated/normalized/rejected entirely in application code, and
  both readers (in-memory + Postgres) filtering identically. Phase 5-11 (frontend
  date-filter UI, frontend variant switcher, final cross-stack verification) are
  untouched; this endpoint is valid and directly callable standalone regardless of
  when the frontend batches land.
- Estimated review budget impact: within the forecast's backend estimate
  (~350-450 lines); self-contained, independently revertible PR 1

### Status
9/23 tasks complete (Phase 1-4 done; Phase 5-11 remain). Ready for the next apply
batch (Phase 5-8: frontend date-filter UI, PR 2) once PR 1 is reviewed/merged, or
for `sdd-verify` to check this batch's backend slice in isolation first.
