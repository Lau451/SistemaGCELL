# Verification Report: admin-stock-movement-history

```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:6ea5e1cbbee8ffde16d4c120f8842ef6b0237a57009d0a736d785b8694ed92c5
verdict: pass
blockers: 0
critical_findings: 0
requirements: 5/5
scenarios: 18/18
test_command: "cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest -q && cd frontend && npm test -- --run"
test_exit_code: 0
build_command: "cd frontend && npx tsc --noEmit"
build_exit_code: 0
```

## Completeness

| Metric | Value |
|--------|-------|
| Tasks total | 16 |
| Tasks complete | 16 |
| Tasks incomplete | 0 |

Both PRs merged to `main`, clean working tree: backend (`b84cadf` code, `6a4cc5e` SDD docs), frontend (`598f1ae` code, `d00066a` SDD docs).

## Build & Tests Execution

- **Build**: PASS — `tsc --noEmit`, 0 errors.
- **Tests**: PASS — backend 294/294, frontend 272/272 (42 files) — 566 total, 0 failed. Re-run fresh this session by both the verify agent and the orchestrator independently (matching counts).

## Spec Compliance Matrix (18/18 scenarios compliant)

| Requirement | Scenario | Test | Result |
|---|---|---|---|
| List Variant Stock Movements Use Case | History newest-first | `test_stock_movement_repository.py::test_list_for_variant_returns_rows_newest_first` | COMPLIANT |
| List Variant Stock Movements Use Case | Cursor pagination, no gaps/dupes | `test_stock_movement_repository.py::test_list_for_variant_paginates_with_strictly_exclusive_before_id_cursor` + `test_admin_stock.py::test_get_movement_history_second_page_items_are_strictly_older_than_first_page` | COMPLIANT |
| List Variant Stock Movements Use Case | Limit clamped, not rejected | `test_list_variant_stock_movements.py::test_limit_is_clamped_and_requested_as_limit_plus_one` + `test_admin_stock.py::test_get_movement_history_limit_above_cap_is_clamped_not_rejected` | COMPLIANT |
| List Variant Stock Movements Use Case | `StockMovementRepository` gains no new method | `test_stock_movement_repository_port.py::test_repository_port_declares_exactly_one_method_record` (pre-existing, still passing) | COMPLIANT |
| Admin Views Per-Variant Movement History | Views variant history newest-first | `stock-history.test.tsx` newest-first test | COMPLIANT |
| Admin Views Per-Variant Movement History | Load more appends, no reset | `stock-history.test.tsx` load-more-append test | COMPLIANT |
| Admin Views Per-Variant Movement History | Empty state | `stock-history.test.tsx` empty-state test | COMPLIANT |
| Admin Views Per-Variant Movement History | Resets to page one on new movement | `stock-history.test.tsx` prop-reference-reset test | COMPLIANT |
| Movement History Ownership Checked | Foreign `variant_id` → 404 | `test_admin_stock.py::test_get_movement_history_for_foreign_variant_id_returns_404_never_403` | COMPLIANT |
| Movement History Ownership Checked | Unknown `variant_id` → 404 | `test_admin_stock.py::test_get_movement_history_for_unknown_variant_id_returns_404` | COMPLIANT |
| Stock Endpoints Require Admin Auth (MODIFIED) | Movement write, no JWT → 401 | `test_admin_stock.py` `post-movement` 401 param case | COMPLIANT |
| Stock Endpoints Require Admin Auth (MODIFIED) | Current-stock read, no JWT → 401 | `test_admin_stock.py` `get-stock` 401 param case | COMPLIANT |
| Stock Endpoints Require Admin Auth (MODIFIED) | Movement history read, no JWT → 401 | `test_admin_stock.py` `get-movement-history` 401 param case | COMPLIANT |
| Variant Stock Movement History Endpoint | Unauthenticated rejected before repo access | same 401 param test, spy asserts zero calls | COMPLIANT |
| Variant Stock Movement History Endpoint | Foreign variant → 404, never 403 | same as above | COMPLIANT |
| Variant Stock Movement History Endpoint | Empty history → 200 empty items | `test_admin_stock.py::test_get_movement_history_for_variant_with_no_movements_returns_empty_page` | COMPLIANT |
| Variant Stock Movement History Endpoint | Limit clamped | `test_admin_stock.py::test_get_movement_history_limit_above_cap_is_clamped_not_rejected` | COMPLIANT |
| Variant Stock Movement History Endpoint | Cursor pagination follows `next_before_id` | `test_admin_stock.py::test_get_movement_history_second_page_items_are_strictly_older_than_first_page` | COMPLIANT |

## Coherence (Design) — all 7 decisions followed

1. `RecordedStockMovement` is a separate frozen DTO in `application/`, not on domain `StockMovement`. Domain `stock_movement.py` byte-unchanged.
2. `PostgresStockMovementHistoryReader` is a new sibling adapter class in a new file, not a method on `PostgresStockMovementRepository`.
3. Clamp (`max(1, min(limit, 100))`) and `limit+1` fetch/trim live in the use case; SQL passes `limit` through as-is.
4. No `ConfigDict` on `AdminStockMovementHistoryItemResponse`/`PageResponse` — matches the existing response-model convention.
5. `stock-history.tsx` is a separate sibling component, rendered below `<StockManager>`.
6. `StockHistory` owns local `useState` for `entries`/`cursor` with compare-during-render reset (no `useEffect`) — deliberate, documented deviation.
7. Proxy allowlists only `limit`/`before_id` into a fresh `URLSearchParams`; an injected extra param is dropped, proven by test.

## TDD Compliance

6/6 checks passed — RED/GREEN/Triangulate/Safety-Net confirmed against actual test files and a fresh full-suite re-run.

## Additional Checks

- No migration file added under `supabase/migrations/` — confirmed (zero diff since prior commit).
- `backend/src/gcell/stock/domain/**` byte-unchanged — confirmed.
- IDOR pattern: a `variant_id` belonging to another product → `404`, never `403` — verified in both the use case code and the test suite.
- `test_domain_boundary.py` — re-run in isolation, 1 passed, unaffected.

## Issues Found

**CRITICAL**: None
**WARNING**: None
**SUGGESTION**:
1. The frontend service-role-boundary test file referenced in generic verify instructions does not exist in this repo — not applicable to this change (it was written for `admin-product-images`), no action needed.
2. ESLint was not independently re-run during this verify pass; only the apply-progress report's prior clean run (0 errors/warnings) was relied on for that signal.

## Verdict

**PASS** — All 16 tasks complete, all 5 requirements / 18 scenarios traced to passing tests re-run fresh this session, all 7 design decisions verified against actual source, domain byte-unchanged, no migration, IDOR pattern confirmed. Ready for `sdd-archive`.
