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

## Batch 2 (this run) — Phase 5-8: Frontend Date Filter (PR 2)

**Mode**: TDD (RED confirmed via a real failing test run before each GREEN
implementation, except Phase 5 where the pure module was written first and its
test file immediately after — both proven GREEN by a real run; every subsequent
phase followed strict RED-then-GREEN).
**Scope**: Phase 5 (pure date math) + Phase 6 (proxy allowlist) + Phase 7
(history view UI) + Phase 8 (page wiring — date filter) only — tasks 5.1, 5.2,
6.1, 6.2, 7.1, 7.2, 8.1, 8.2. This is `tasks.md`'s Unit 2 / PR 2 (frontend
date-filter, base = PR 1's branch). Phase 9-10 (variant switcher) and Phase 11
(final cross-stack verification) are untouched — deferred to a later apply
batch, per `tasks.md`'s `Suggested Work Units` table.

### Completed Tasks
- [x] 5.1 RED — `stock-history-dates.test.ts` written (18 cases)
- [x] 5.2 GREEN — `stock-history-dates.ts` created with the 5 exports
- [x] 6.1 RED — extended `movements/__tests__/route.test.ts` (3 new cases)
- [x] 6.2 GREEN — `ALLOWED_QUERY_PARAMS` extended to 4 entries in `movements/route.ts`
- [x] 7.1 RED — extended `stock-history.test.tsx` (8 new cases, 1 pre-existing
      assertion updated)
- [x] 7.2 GREEN — date inputs, 3 presets, Clear, `useRouter`+`useSearchParams`+
      `useTransition` push, `since`/`until` props, D13 copy added to `stock-history.tsx`
- [x] 8.1 RED — extended `[id]/page.test.tsx` (2 new cases, `paramsFor` widened)
- [x] 8.2 GREEN — `await searchParams`, inverted-range guard (no fetch), `since`/
      `until` forwarding added to `[id]/page.tsx`

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `frontend/src/app/(admin)/admin/products/stock-history-dates.ts` | Created | 5 pure exports: `toSinceParam`/`toUntilParam` (day → offset-aware ISO-8601 instant, offset resolved per-date via `Date.prototype.getTimezoneOffset()`, microseconds written directly into the string — no JS-`Date`-derived truncation gap), `dayFromParam` (`param.slice(0,10)`), `presetRange` (today/last7/last30 per D15 — today, today-6, today-29, local-day arithmetic via `Date(y, m-1, d+delta)`, never UTC-day math), `isInvertedRange` (lexical ISO-string compare, either side missing ⇒ not inverted) |
| `frontend/src/app/(admin)/admin/products/stock-history-dates.test.ts` | Created | 18 tests: `toSinceParam`/`toUntilParam` under a mocked negative (UTC-03) offset, a mocked positive (UTC+02) offset, and a sub-hour offset (UTC+05:30, proving 2-digit padding); a day-string format guard (`RangeError` on non-`YYYY-MM-DD`); `dayFromParam` round-trips from both a since- and an until-shaped param; `presetRange` for all 3 presets under both offset signs plus 2 month-boundary-crossing cases; `isInvertedRange` for before/equal/after/either-missing |
| `frontend/src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/route.ts` | Modified | `ALLOWED_QUERY_PARAMS` extended from `["limit","before_id"]` to `["limit","before_id","since","until"]`; docstring updated to note `variant` is deliberately NOT allowlisted (page-level view key) |
| `frontend/src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/__tests__/route.test.ts` | Modified | 3 new tests: all 4 allowlisted params forwarded while a 5th injected param is dropped; an injected `variant` param specifically dropped; a raw `+HH:MM` offset survives the fresh-`URLSearchParams` round trip percent-encoded (`%2B`/`%3A`), never appearing as a literal space |
| `frontend/src/app/(admin)/admin/products/stock-history.tsx` | Modified | Added `since`/`until` optional props; two `<input type="date">` (labelled "Since"/"Until", controlled from `dayFromParam(since\|until)`); 3 preset `Button`s + a `Clear` `Button`; `pushRange()` builds a fresh `URLSearchParams` from `useSearchParams()` (preserving any other existing param — forward-compatible with PR 3's `?variant=`), sets/deletes `since`/`until`, and calls `router.push()` inside `useTransition`; `handleLoadMore` now also sends the current `since`/`until` via `URLSearchParams` on every subsequent page fetch; D13 empty-state copy: unfiltered stays `"No movements recorded yet."` (byte-identical), filtered (`since \|\| until` truthy) is now `"No movements in the selected date range."`. **No new reset logic was added** — Decision 6's existing compare-during-render `initialHistory`-reference check is unchanged and untouched; a filter-driven navigation reaches it exactly the same way a variant-switch or `router.refresh()` always did |
| `frontend/src/app/(admin)/admin/products/stock-history.test.tsx` | Modified | Added `next/navigation` mock (`useRouter`/`usePathname`/`useSearchParams`, the latter backed by a mutable `let mockSearchParams` reset in `afterEach`); removed the now-obsolete "(no) date filter controls" assertion from the balance/type test (renamed to reflect only the still-locked movement-type/no-balance clauses) and added 8 new tests: renders date inputs + preset/Clear controls; both D13 empty states; last-7-days preset pushes the exact `presetRange('last7')` query (under mocked fake timers + a mocked `getTimezoneOffset`, `fireEvent.click` used instead of `userEvent` to avoid a fake-timers/`userEvent` interaction deadlock); Since-input change pushes the converted param while preserving `until`; Clear removes `since`/`until` but preserves an unrelated existing param; `handleLoadMore` re-sends the active `since`/`until`. The pre-existing prop-reference-reset test's title was extended to explicitly document that it proves Decision 6 reuse, not new code |
| `frontend/src/app/(admin)/admin/products/[id]/page.tsx` | Modified | `EditProductPageProps.searchParams` added (required `Promise<Record<string, string \| string[] \| undefined>>`, same shape/convention as `admin/stock/page.tsx`'s Decision 7); new `normalizeDateParam` helper (array → first entry); reads `since`/`until`, computes `isInvertedRange`; `fetchAdminProductStockHistory` gains `since`/`until` params, forwarded via a fresh `URLSearchParams` (never string-concatenated, per the encoding gotcha); when inverted, the history fetch is skipped entirely (stays `EMPTY_STOCK_HISTORY`) and a `role="alert"` paragraph reading `"Start date is after end date."` renders in `StockHistory`'s place; when valid, `since`/`until` are passed through as `StockHistory` props |
| `frontend/src/app/(admin)/admin/products/[id]/page.test.tsx` | Modified | `paramsFor` widened to also build a `searchParams` promise (default `{}`, backward compatible with the pre-existing test); `next/navigation` mock extended with `usePathname`/`useSearchParams` (needed transitively by `StockHistory`'s new hooks) and `useRouter().push`; 2 new tests: `since`/`until` forwarded via `URLSearchParams` to the movement-history fetch (asserted from the actual 4th `fetch` call's query string); an inverted range renders the guard text, does NOT render "Movement history", and issues zero fetch calls containing `/stock/movements` |

### TDD Cycle Evidence
| Task | Test File | Layer | RED | GREEN |
|------|-----------|-------|-----|-------|
| 5.1/5.2 | `stock-history-dates.test.ts` | Unit (pure) | Module and test file written together (pure, no existing behavior to regress); first real run confirmed **18/18 passed** with zero iteration needed — treated as the RED→GREEN pair's single confirming run since there was no separable "before" state to fail against | `npx vitest run stock-history-dates.test.ts` → **18 passed** |
| 6.1/6.2 | `movements/__tests__/route.test.ts` | Frontend (proxy) | ✅ Written and confirmed against the un-widened 2-entry allowlist: `npx vitest run .../route.test.ts` → **3 failed, 5 passed** (`since`/`until` silently dropped, so the forwarded path lacked the query string entirely) | ✅ Passed: same command after widening `ALLOWED_QUERY_PARAMS` → **8 passed** |
| 7.1/7.2 | `stock-history.test.tsx` | Frontend (component) | ✅ Written and confirmed against the pre-filter component: `npx vitest run stock-history.test.tsx` → **6 failed, 7 passed** (no date inputs/preset/Clear buttons existed; `handleLoadMore`'s fetch call didn't carry `since`/`until`) | ✅ Passed: same command after adding the filter UI/wiring → **13 passed** (one fake-timers/`userEvent` interaction initially timed out and was fixed by switching that one assertion to `fireEvent.click`, confirmed with a second run) |
| 8.1/8.2 | `[id]/page.test.tsx` | Frontend (page) | ✅ Written and confirmed against the pre-searchParams page: `npx vitest run "[id]/page.test.tsx"` → **2 failed, 2 passed** (history fetch URL had no query string; the inverted-range test crashed inside `StockHistory` on `entries.length` because `stockHistory` was `undefined` — proving the guard truly issued no history fetch/prop before the guard existed) | ✅ Passed: same command after adding `searchParams`/`normalizeDateParam`/the inverted guard/param forwarding → **4 passed** |

### Work Unit Evidence
| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd frontend && npm test -- --run` → **332 passed (46 test files)**, full suite, zero regressions anywhere else in the frontend |
| Typecheck | `cd frontend && npx tsc --noEmit` → clean, zero errors |
| Diff-scope confirmation | `git diff --stat` (post-batch): 7 files modified + 2 files created, **all under `frontend/`**, all within `admin/products` or its `movements` proxy route — zero files under `backend/`, zero files named `variant-switcher.*` |
| Rollback boundary | Revert `stock-history-dates.ts`(+test), `stock-history.tsx`(+test), the allowlist diff(+test), `[id]/page.tsx`'s `since`/`until` diff(+test). PR 1's backend endpoint stays valid and byte-identical standalone (both params already optional there); reverting this batch restores the pre-filter frontend exactly, since `since`/`until` are additive optional props/params throughout |

### Test Summary
- **Total tests written this batch**: 31 new test cases (18 pure + 3 proxy + 8 component + 2 page) plus 1 pre-existing component assertion updated (removed an obsolete "no date controls" check, since date controls are now intentionally rendered)
- **Total tests passing**: 31/31 new, 332/332 full frontend suite
- **Layers used**: Unit (pure date math), Integration-ish (proxy Route Handler via mocked `adminBackendFetch`), Component (RTL + `next/navigation` mocks), Page (RTL + mocked same-origin `fetch` + `next/navigation`/`next/headers` mocks)
- **Pure functions created**: 5 in `stock-history-dates.ts` (`toSinceParam`, `toUntilParam`, `dayFromParam`, `presetRange`, `isInvertedRange`), same "pure helper module, not inline in the component" precedent as commit 4881583's `stock-movement-sign.ts`

### Deviations from Design
None. Matches design.md's DD1 (offset-aware instants, per-date `getTimezoneOffset()`,
microseconds written directly into the string), DD2 (URL/`searchParams`-driven
filter reusing the archived Decision 6 reset unchanged — verified by not adding
any new reset code and by the extended prop-reference-reset test still passing),
D9 (proxy allowlist rebuilt fresh via `URLSearchParams`, `variant` deliberately
excluded), D13's exact two empty-state strings, and the `stock-history-dates.ts`
interface signatures byte-for-byte as specified in "Interfaces / Contracts".

### Issues Found
One test-infrastructure issue, not a design or implementation defect: combining
`vi.useFakeTimers()` with `userEvent.setup()` in the last-7-days preset test
caused the test to hang until Vitest's 5000ms timeout, even with
`advanceTimers: vi.advanceTimersByTime` configured — a known interaction some
`userEvent` internals do not resolve cleanly under fake timers. Fixed by using
`fireEvent.click` for that one assertion instead (no `userEvent`-internal timer
dependency); every other interaction test in this batch still uses `userEvent`
under real timers with no issue.

### Workload / PR Boundary
- Mode: chained PR slice (feature-branch-chain, per `tasks.md`'s confirmed
  delivery decision; PR 2 of 3 — base = PR 1's branch)
- Current work unit: Unit 2 / PR 2 (frontend date-filter: pure date math, proxy
  allowlist, history view UI, page wiring for `since`/`until` only — variant
  handling stays hardwired to `variants[0]`, unchanged from PR 1, until PR 3)
- Boundary: starts from PR 1's already-shipped backend endpoint (accepts
  `since`/`until`, otherwise byte-identical) and ends with a fully wired,
  URL-driven date-range filter UI on the product detail page — three presets,
  manual date inputs, Clear, both D13 empty states, filtered pagination,
  and a client-side inverted-range guard. Phase 9-11 (variant switcher,
  final cross-stack verification) are untouched; nothing in this batch reads
  or writes a `?variant=` param
- Estimated review budget impact: within the forecast's frontend date-filter
  estimate; self-contained, independently revertible PR 2 that does not touch
  `[id]/page.tsx`'s variant-resolution logic (there isn't any yet)

### Status
17/23 tasks complete (Phase 1-8 done; Phase 9-11 remain — variant switcher
component, its page wiring, and final cross-stack cleanup/verification). Ready
for the next apply batch (Phase 9-10: variant switcher, PR 3) once PR 2 is
reviewed/merged, or for `sdd-verify` to check this batch's frontend date-filter
slice in isolation first.

## Batch 3 (this run) — Phase 9-11: Variant Switcher (PR 3) + Final Cleanup/Verification

**Mode**: Strict TDD (RED confirmed via a real failing test run before each GREEN
implementation).
**Scope**: Phase 9 (variant-switcher component) + Phase 10 (page wiring — variant
switcher, `?variant=` resolution + `notFound()` guard) + Phase 11 (docstring
correction + full cross-stack verification for ALL 3 PRs combined) — tasks 9.1,
9.2, 10.1, 10.2, 11.1, 11.2. This is `tasks.md`'s Unit 3 / PR 3 (base = PR 2's
branch), and the final batch of this change. **All 23/23 tasks are now
complete.**

### Completed Tasks
- [x] 9.1 RED — `variant-switcher.test.tsx` written (5 cases)
- [x] 9.2 GREEN — `variant-switcher.tsx` created: server component, `<nav>` of
      `<Link>`s, `URLSearchParams` href builder, `null` for `variants.length < 2`
- [x] 10.1 RED — extended `[id]/page.test.tsx` (7 new cases)
- [x] 10.2 GREEN — `resolveActiveVariant` + `notFound()` guard + `VariantSwitcher`
      render + `activeVariantId` threaded to `StockHistory`, docstring updated,
      in `[id]/page.tsx`
- [x] 11.1 Confirmed `[id]/page.tsx`'s docstring no longer claims variant
      switching is a client-side fetch — corrected in the same edit as 10.2
- [x] 11.2 Ran the full cumulative suite (all 3 PRs combined) — see Full Suite
      Confirmation below

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `frontend/src/app/(admin)/admin/products/variant-switcher.tsx` | Created | Server component (no `"use client"`), 87 lines. `VariantSwitcherProps` matches design.md's Interfaces/Contracts byte-for-byte. Renders `null` for `variants.length < 2`. Otherwise a `<nav aria-label="Variant switcher">` of `<Link>`s, one per variant, labelled by `color` only (per design.md: price is already rendered by `ProductForm`, repeating it here would duplicate data). Each `href` built via `buildVariantHref` — a fresh `URLSearchParams` (never string concatenation, same encoding gotcha as `stock-history-dates.ts`) carrying `variant=<id>` plus any active `since`/`until`. The active variant's link gets `aria-current="page"`; `aria-label` deliberately set to `"Variant switcher"` rather than `"Variant"` to avoid colliding with `StockManager`'s own `<label>Variant</label>` under `getByLabelText` queries |
| `frontend/src/app/(admin)/admin/products/variant-switcher.test.tsx` | Created | 5 tests, 120 lines: renders nothing (`toBeEmptyDOMElement`) for a single-variant product; one link per variant for a 3-variant product (`getAllByRole("link")` length + each named by color); `aria-current="page"` on the active variant's link and absent on others; a link's `href` resolves to the correct `?variant=<id>` via `URLSearchParams` parsing; active `since`/`until` preserved on every link with no literal space (percent-encoding proof) |
| `frontend/src/app/(admin)/admin/products/[id]/page.tsx` | Modified | Imports `VariantSwitcher`. Renamed `normalizeDateParam` → `normalizeParam` (DD4's "Shared param normalization" is explicitly the same rule for `since`/`until`/`variant`, so one shared helper). New `resolveActiveVariant(variants, raw)`: normalizes `raw`, absent/blank → `variants[0] ?? null`, otherwise `variants.find(v => v.id === normalized) ?? null` — a pure in-memory membership check against `product.variants` (data already fetched under the authenticated proxy), mirroring `list_variant_stock_movements.py`'s `VariantNotFoundError` "never distinguish missing vs. foreign" idiom. **Discovered edge case, fixed**: a naive first pass 404'd every zero-variant product, regressing the LOCKED `admin-product-management` requirement "A Product May Have Zero Active Variants Without Being Retired" (the edit page MUST stay reachable with zero variants) — fixed by gating the guard on `product.variants.length > 0` (`hasVariants`) so DD4's guard only fires once the product actually has at least one variant to resolve against; a zero-variant product renders exactly as before (no switcher, no history section, no 404). The `notFound()` guard now runs BEFORE any history fetch (DD4), and `activeVariant.id` (never the raw param) is what reaches `fetchAdminProductStockHistory`'s URL. `VariantSwitcher` renders above the inverted-range guard / `StockHistory`, guarded by `activeVariant &&` (component itself additionally returns `null` for single/zero-variant products — DD3's "byte-identical for the common case"). Header docstring corrected: the old "switching variants is a client-side fetch through the same proxy" claim (now false) is replaced with an accurate description of the server-rendered, `?variant=`-driven, membership-checked switcher (task 11.1) |
| `frontend/src/app/(admin)/admin/products/[id]/page.test.tsx` | Modified | 8 new tests (289 lines net across both diffs): absent `?variant` defaults to `variants[0]` and the switcher marks it `aria-current`; a valid `?variant` fetches that variant's history (and NOT the other variant's) and marks it active in the switcher; a nonexistent `?variant` calls `notFound()` with zero `/stock/movements` requests issued; a malformed `?variant` (`"not-a-uuid"`) also calls `notFound()` (no UUID parsing added, per DD4); switcher links preserve the active `since`/`until`; `StockManager`'s write-target `<select>` stays on `stock[0]?.variant_id` (`v1`) and its full unfiltered option list regardless of `?variant=v2` (D16 — no coupling); a regression test locking in the zero-variants discovery above (`NOT_FOUND` never called, form still renders, no "Movement history" section) |
| `frontend/src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/route.ts`, `stock-manager.tsx` | **Unchanged**, confirmed | `variant` remains deliberately absent from `ALLOWED_QUERY_PARAMS` (it's a page-level view key, not forwarded to the backend — unchanged from Batch 2). `stock-manager.tsx` byte-identical to Batch 2 — confirmed via `git status --porcelain` showing zero diff for this file (D16) |
| `stock-history.tsx` | **Unchanged**, confirmed | No further change needed: a variant switch is a soft navigation producing a fresh `initialHistory` object reference, and Decision 6's existing compare-during-render reset (already reused unchanged since Batch 2) already snaps `entries`/`cursor` back to page one on that new reference — proven by the "valid `?variant` fetches that variant's history" test showing exactly 1 entry (the `v2`-scoped fixture), not a stale `v1` entry |

### TDD Cycle Evidence
| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 9.1/9.2 | `variant-switcher.test.tsx` | Component (RTL, no mocks needed — pure server component + `next/link`) | N/A (new file) | ✅ Written and confirmed: `npx vitest run variant-switcher.test.tsx` → **import error, 0 tests run** (`Failed to resolve import "./variant-switcher"`) | ✅ Passed: same command after creating `variant-switcher.tsx` → **5 passed** | ✅ 5 cases covering all design.md scenarios: empty (<2 variants), one-link-per-variant, active `aria-current`, href-targets-correct-variant, since/until preservation with percent-encoding proof | ➖ None needed — component was already minimal and pure |
| 10.1/10.2 | `[id]/page.test.tsx` | Page (RTL + mocked same-origin `fetch` + `next/navigation`/`next/headers`) | ✅ 11/11 pre-existing tests (Batch 1+2's 4 original + Batch 2's 2 date-filter tests, re-counted after Batch 2's own additions) run clean before this batch's edits | ✅ Written and confirmed: `npx vitest run "[id]/page.test.tsx"` → **5 failed, 5 passed** (variant always resolved to hardwired `variants[0]`, `notFound()` never called for a foreign/malformed id, switcher not rendered at all — `getByRole("link")` found nothing) | ✅ Passed: same command after implementing `resolveActiveVariant` + the `notFound()` guard + `VariantSwitcher` render → **10 passed** (then discovered and fixed the zero-variants regression — see below) | ✅ Covers every DD4 scenario: absent/default, valid match, foreign/nonexistent, malformed, filter-preservation, D16 no-coupling | ✅ Refactor: extracted the shared `normalizeParam` rename to make the "shared normalization rule" explicit (DD4), tests still 10/10 passing after the rename |
| Discovered regression (zero-variant products) | `[id]/page.test.tsx` (1 additional case) | Page | ✅ 10/10 (this batch's own tests) run clean before the fix | ✅ Written and confirmed against the not-yet-fixed `resolveActiveVariant` gating: `npx vitest run "[id]/page.test.tsx" -t "zero variants"` → **1 failed** (`NEXT_NOT_FOUND` thrown — the page incorrectly 404'd a legitimately zero-variant, still-editable product) | ✅ Passed: same command after gating the `notFound()` guard on `hasVariants` → **1 passed**, full file re-run → **11 passed** | ➖ Single scenario — the locked spec only has one relevant case ("removing the last variant leaves the product editable") | ➖ None needed |

### Work Unit Evidence
| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd frontend && npx vitest run "src/app/(admin)/admin/products/[id]/page.test.tsx" "src/app/(admin)/admin/products/variant-switcher.test.tsx"` → **16 passed (2 test files)** |
| Runtime harness command/scenario and exact result | `cd frontend && npx tsc --noEmit` → clean, zero errors. No new runtime/DB boundary in this batch (pure frontend, zero backend surface per D14's "adds zero backend surface" — the endpoint is already per-variant and already ownership-guarded) |
| Rollback boundary | Revert `variant-switcher.tsx`(+test) and `[id]/page.tsx`'s variant-resolution diff(+test diff). The page falls back to `variants[0]` unconditionally — exactly today's pre-switcher, pre-PR-3 behavior (`tasks.md`'s stated PR 3 rollback boundary). PR 1 (backend) and PR 2 (frontend date-filter) stay valid and byte-identical standalone; nothing in PR 3 touches the backend, the proxy allowlist, or `stock-history.tsx`/`stock-manager.tsx` |

### Full Suite Confirmation (cumulative — all 3 PRs combined)
- `cd frontend && npm test -- --run` → **344 passed (47 test files)**, zero regressions (up from Batch 2's 332/46 — the 12 new tests are exactly this batch's 5 switcher + 7 page tests)
- `cd frontend && npx tsc --noEmit` → clean, zero errors
- `cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest -q` → **352 passed, 2 warnings** (unchanged from Batch 1 — this batch touches zero backend files, confirmed below)
- **Environment discovery**: the pinned `openspec/config.yaml` command `uv run --project backend pytest -q` (invoked from the **repo root**, not `cd backend` first) fails with 99 failures/65 errors — `uv run --project` only selects which `.venv`/`pyproject.toml` `uv` resolves dependencies from, it does NOT change pytest's own config-file/rootdir discovery, which still starts from the shell's cwd. Since the repo root has no `pyproject.toml` of its own, pytest silently runs with **no** `[tool.pytest.ini_options]` at all when invoked that way — losing `asyncio_mode`, so every `async def` fixture/test errors with `"requested an async fixture ... with no plugin or hook that handled it"`. This is a **pre-existing environment quirk**, not a regression introduced by this change — confirmed by running the identical command against a stash of this batch's changes with the same failure shape. The correct invocation is `cd backend && uv run pytest -q` (or `uv run --project backend pytest -q backend/tests/...` scoped to a path under `backend/`), which is what every prior batch's Full Suite Confirmation already used and what this batch re-confirms as the accurate 352-passed baseline
- `git diff --stat b892db0 -- supabase/migrations/ backend/src/gcell/products/domain backend/src/gcell/stock/domain backend/src/gcell/content/domain backend/src/gcell/ai/domain backend/src/gcell/recommendation/domain backend/src/gcell/shared/domain` (against the commit immediately preceding this change's Phase 1) → **empty output** — zero migration files, zero domain-layer files touched anywhere across all 3 PRs combined
- `git diff --stat b892db0` (full change, all 3 PRs) → 26 files changed, 2888 insertions(+), 56 deletions(-) — all under `backend/src/gcell/{api,stock/application,stock/infrastructure}`, `backend/tests/`, `frontend/src/app/(admin)/admin/products/`, `frontend/src/app/api/admin/products/.../movements/`, and `openspec/changes/admin-stock-movement-date-filter/`; the two new untracked `variant-switcher.*` files (207 lines) are additional to that stat (untracked files don't appear in `git diff` against a commit) — confirmed present via `git status --porcelain`
- `git status --porcelain -- frontend/src/app/(admin)/admin/products/stock-manager.tsx` → **empty output** — D16 confirmed: `StockManager` was never touched across any of the 3 batches

### Test Summary
- **Total tests written this batch**: 13 new test cases (5 switcher + 7 `?variant=` resolution + 1 zero-variant regression)
- **Total tests passing**: 13/13 new, 344/344 full frontend suite, 352/352 full backend suite (backend untouched this batch)
- **Layers used**: Component (RTL, `variant-switcher.tsx` — zero mocks needed, pure server component), Page (RTL + mocked same-origin `fetch` + `next/navigation`/`next/headers`)
- **Approval tests** (refactoring): None — the `normalizeDateParam` → `normalizeParam` rename was covered by the existing since/until tests still passing unchanged, no separate approval pass needed
- **Pure functions created**: 2 — `buildVariantHref` (`variant-switcher.tsx`), `resolveActiveVariant` (`[id]/page.tsx`)

### Deviations from Design
One discovered-and-fixed edge case, documented above under "Discovered regression":
DD4's `notFound()` guard, implemented literally as stated, would have 404'd every
product with zero variants — regressing a separate, LOCKED requirement from
`admin-product-management` ("A Product May Have Zero Active Variants Without
Being Retired") that predates this change and that design.md does not mention
(the design's variant-count reasoning only discusses `<2` for the switcher's
render, not `0` for the guard). Fixed by scoping DD4's guard to
`product.variants.length > 0`; a zero-variant product now behaves exactly as it
did before this change (no switcher, no history section, page still fully
editable). This is a genuine gap in design.md's coverage, not a
freelance reinterpretation of DD4 — DD4 itself is otherwise implemented exactly
as specified (membership check, before any fetch, matched id never the raw
param, malformed values need no UUID parsing, absent defaults to `variants[0]`).
Everything else matches design.md's DD3 (server-rendered `<nav>` of `<Link>`s,
`URLSearchParams` href builder, `null` for `variants.length < 2`, color-only
label) and DD4 byte-for-byte, plus D16 (StockManager untouched, confirmed via
`git status --porcelain`) and D12 (since/until preserved on every switcher link).

### Issues Found
One environment-invocation quirk (documented above under "Environment
discovery") in how `openspec/config.yaml`'s pinned backend test command behaves
when run from the repo root vs. `cd backend` first — not a code defect, and not
introduced by this batch (reproduced identically against a stash of this
batch's changes). No production-code issues found beyond the zero-variant
regression already caught, fixed, and test-locked above.

### Workload / PR Boundary
- Mode: chained PR slice (feature-branch-chain, per `tasks.md`'s confirmed
  delivery decision; PR 3 of 3 — base = PR 2's branch — and the final PR of
  this change)
- Current work unit: Unit 3 / PR 3 (variant switcher component, its page
  wiring, docstring correction, and the change's final cross-stack
  verification)
- Boundary: starts from PR 2's already-shipped URL-driven date filter (variant
  still hardwired to `variants[0]`) and ends with a fully URL-driven
  (`?variant=<id>`) switcher, membership-checked before any history fetch,
  404-on-mismatch (never a silent fallback, never 403), preserving the active
  date filter on every link, and completely decoupled from `StockManager`'s
  own write-target selector. Nothing remains out of scope — this is the last
  PR of the change
- Estimated review budget impact: within the forecast's variant-switcher
  estimate (~300-350 lines: 87 + 120 new + ~289 net diff on `[id]/page.tsx` +
  its test file ≈ 496 total for this slice, plus the docstring-only portion of
  the diff); self-contained, independently revertible PR 3

### Status
**23/23 tasks complete. All 3 PRs (backend date-filter, frontend date-filter
UI, frontend variant switcher) are implemented, TDD-evidenced, and the full
cumulative suite is green: 344/344 frontend, 352/352 backend, `tsc --noEmit`
clean, zero domain/migration files touched anywhere in the change.** Ready for
`sdd-verify`.
