# Tasks: Admin Stock Movement Date Filter

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1150-1400 (backend ~350-450, frontend date-filter ~600-700, frontend variant-switcher ~300-350) |
| 400-line budget risk | High — every unit meets/exceeds the 400-line per-PR guideline, and the combined total sits at/above the 1200-line session budget |
| Chained PRs recommended | Yes |
| Suggested split | PR1 (backend date-filter + both spec deltas) → PR2 (frontend date-filter UI) → PR3 (frontend variant switcher) |
| Delivery strategy | ask-on-risk |
| Chain strategy | feature-branch-chain (recommended — PR3 edits the same `[id]/page.tsx` region PR2 introduces; confirm with user before apply) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: feature-branch-chain
400-line budget risk: High

Rationale for 3 units, not 2: the proposal's own suggested 2-way split (backend | combined
frontend) still leaves the frontend unit alone at ~900-1050 lines — over double the per-PR
budget. `[id]/page.tsx` and the URL-model (DD2/DD3) are the natural seam: PR2 lands the
URL-driven date filter only (`?since`/`?until`); PR3 layers `?variant=` on top of that same
model, exactly the sequencing D14/DD2's "Update" note describes. This keeps each unit
independently reviewable and revertible without leaving `[id]/page.tsx` in a half-wired state.

### Suggested Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | `InvertedDateRangeError`, use-case `since`/`until` (tz-normalize, midnight expansion, inverted raise), port + both readers, `admin.py` params, both spec deltas | PR 1 | `cd backend && uv run pytest tests/unit/stock/test_list_variant_stock_movements.py tests/integration/db/test_stock_movement_repository.py tests/integration/api/test_admin_stock.py -v` | Local Supabase Postgres (`require_db_pool` harness) | Revert `exceptions.py`, `list_variant_stock_movements.py`, `stock_movement_history_reader.py`, both readers, `admin.py` diff; both params optional (D7) — revert restores byte-identical behavior |
| 2 | `stock-history-dates.ts`, proxy allowlist → 4, `stock-history.tsx` date UI, `[id]/page.tsx` since/until forwarding + inverted guard | PR 2 (base = PR1 branch) | `cd frontend && npm test -- stock-history-dates.test.ts stock-history.test.tsx "movements/__tests__/route.test.ts" "[id]/page.test.tsx"` | `npm run dev` against PR1's live endpoint; manual date-input + preset click-through | Revert `stock-history-dates.ts`, `stock-history.tsx`, allowlist diff, `[id]/page.tsx` since/until diff; PR1's endpoint stays valid standalone |
| 3 | `variant-switcher.tsx`, `[id]/page.tsx` `resolveActiveVariant` + `notFound()` guard + switcher render | PR 3 (base = PR2 branch) | `cd frontend && npm test -- variant-switcher.test.tsx "[id]/page.test.tsx"` | `npm run dev`; manual variant-link click-through + a hand-typed foreign `?variant=` id | Revert `variant-switcher.tsx`, `[id]/page.tsx`'s variant-resolution diff; page falls back to `variants[0]` unconditionally (today's exact behavior, D14 rollout note) |

## Phase 1: Backend Foundation (PR 1)

- [x] 1.1 Add `InvertedDateRangeError(ValueError)` to `backend/src/gcell/stock/application/exceptions.py`.
- [x] 1.2 Add optional `since`/`until` (default `None`) to the `StockMovementHistoryReader` protocol in `stock_movement_history_reader.py`.

## Phase 2: Use Case Date Filtering (PR 1)

- [x] 2.1 RED — extend `tests/unit/stock/test_list_variant_stock_movements.py`: naive-datetime → UTC normalize; midnight-`until` expands to `+1 day − 1µs`; `since == until` valid; `since > until` → `InvertedDateRangeError`; ownership guard runs first (foreign variant + inverted range → `VariantNotFoundError`, zero reader calls); both `None` → today's exact call shape.
- [x] 2.2 GREEN — implement `since`/`until` params, tz-normalize, expansion, inverted-range raise in `list_variant_stock_movements.py`.

## Phase 3: Infrastructure Readers (PR 1)

- [x] 3.1 RED — extend `InMemoryStockMovementHistoryReader`'s fixture usage (feeds 2.1) to cover `since`/`until` filtering.
- [x] 3.2 GREEN — implement `since`/`until` filtering in `in_memory_stock_movement_history_reader.py`.
- [x] 3.3 RED — extend `tests/integration/db/test_stock_movement_repository.py`: boundary rows at `since`/`until` included; range + `before_id` compound predicate is gap-free across pages; variant isolation under a filter.
- [x] 3.4 GREEN — add `$4`/`$5` predicates to `postgres_stock_movement_history_reader.py`, `$3` stays `limit`.

## Phase 4: API Wiring (PR 1)

- [x] 4.1 RED — extend `tests/integration/api/test_admin_stock.py`: `?since`/`?until` filter; inverted range → 422 body from `str(exc)`; `?since=abc` → 422 not 500; omitting both is byte-identical to current response; 404 for foreign variant still precedes 422.
- [x] 4.2 GREEN — add two optional `datetime` params to `admin.py`, pass through, no `Query()`, no new `except` arm.
- [x] 4.3 Confirm `specs/admin-stock-management/spec.md` and `specs/admin-api-access/spec.md` deltas match shipped behavior (D4/D5 clauses carried verbatim, unchanged).

## Phase 5: Pure Date Math (PR 2)

- [x] 5.1 RED — create `stock-history-dates.test.ts`: `toSinceParam`/`toUntilParam` under mocked negative + positive TZ offset; `dayFromParam` round-trip; `presetRange` for today/last7/last30 (D15); `isInvertedRange` lexical compare.
- [x] 5.2 GREEN — create `frontend/src/app/(admin)/admin/products/stock-history-dates.ts` with the 5 exports.

## Phase 6: Proxy Allowlist (PR 2 — threat matrix: HTTP query passthrough)

- [x] 6.1 RED — extend `movements/__tests__/route.test.ts`: exactly four params forwarded; a fifth injected param dropped; an injected `variant` param dropped; `+HH:MM` offset survives encoding.
- [x] 6.2 GREEN — extend `ALLOWED_QUERY_PARAMS` to `["limit","before_id","since","until"]` in `movements/route.ts`.

## Phase 7: History View UI (PR 2)

- [x] 7.1 RED — extend `stock-history.test.tsx`: preset click pushes correct query and preserves `variant`; both D13 empty states; `handleLoadMore` re-sends `since`/`until`; new `initialHistory` reference resets entries+cursor.
- [x] 7.2 GREEN — add date inputs, 3 presets, Clear, `useRouter`+`useTransition` push, `since`/`until` props, D13 copy to `stock-history.tsx`.

## Phase 8: Page Wiring — Date Filter (PR 2)

- [x] 8.1 RED — extend `[id]/page.test.tsx`: inverted URL renders guard copy and issues no fetch; `since`/`until` forwarded via `URLSearchParams` to the history fetch.
- [x] 8.2 GREEN — `await searchParams` for `since`/`until`, inverted-range guard (no fetch), forward params in `[id]/page.tsx` (variant handling stays hardwired to `variants[0]` until PR 3).

## Phase 9: Variant Switcher Component (PR 3)

- [x] 9.1 RED — create `variant-switcher.test.tsx`: one link per variant labelled by `color`; `aria-current="page"` on active; hrefs carry `?variant=` and active `since`/`until` (D12); renders nothing for a single-variant product; offset percent-encoded, not a space.
- [x] 9.2 GREEN — create `variant-switcher.tsx`: server component, `<nav>` of `<Link>`s, `URLSearchParams` href builder, `null` for `variants.length < 2`.

## Phase 10: Page Wiring — Variant Switcher (PR 3 — threat matrix: IDOR-adjacent `?variant=`)

- [x] 10.1 RED — extend `[id]/page.test.tsx`: absent `?variant` → `variants[0]`; valid `?variant` → that variant's history; foreign/nonexistent/malformed `?variant` → `notFound()`, movements proxy NOT called; matched variant's own id used in the fetch URL, never the raw param; `StockManager` output unaffected by `?variant`.
- [x] 10.2 GREEN — implement `resolveActiveVariant`, wire the `notFound()` guard before any fetch, render `VariantSwitcher`, pass `activeVariantId` to `StockHistory`, update the file header docstring in `[id]/page.tsx`.

## Phase 11: Cleanup

- [x] 11.1 Confirm `[id]/page.tsx`'s docstring no longer claims variant switching is a client-side fetch.
- [x] 11.2 Run `npm --prefix frontend test && uv run --project backend pytest -q` after PR 3 to confirm the cumulative change set is green.
