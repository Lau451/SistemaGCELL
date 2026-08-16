# Apply Progress: Admin Stock Page

## Batch 1 (this run) — Phase 1-2: Backend (PR 1)

**Mode**: Strict TDD
**Scope**: Phase 1 (use case) + Phase 2 (route + response model) only — tasks 1.1, 1.2, 2.1, 2.2.
Phase 3 (frontend proxy), Phase 4 (frontend page), Phase 5 (nav link), and Phase 6
(full-suite verification across both stacks) are untouched — out of scope for this
batch, deferred to a later apply run once PR 1 merges (tasks.md's chained-PR split,
Unit 1 / PR 1).

### Completed Tasks
- [x] 1.1 RED `backend/tests/unit/stock/test_list_catalog_stock_levels.py` (new)
- [x] 1.2 GREEN `backend/src/gcell/stock/application/list_catalog_stock_levels.py` (new)
- [x] 2.1 RED extend `backend/tests/integration/api/test_admin_stock.py`
- [x] 2.2 GREEN `backend/src/gcell/api/admin.py` (response model + route)

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `backend/tests/unit/stock/test_list_catalog_stock_levels.py` | Created | 11 unit tests: empty catalog → `[]`; `below=None` → unfiltered; ascending sort incl. full tiebreaker chain (`quantity_on_hand`, `product_name.casefold()`, `color.casefold()`, `str(variant_id)`); `below=0` → only zero-quantity rows; `below=-5` clamps to `0` (never raises); case-insensitive substring match on product name; on variant color; blank/whitespace search ignored; `below`+search AND-combine; SQL-injection-shaped search string (`"'; DROP TABLE products;--"`) returns `[]` safely; `CatalogStockRow` field carry-through |
| `backend/src/gcell/stock/application/list_catalog_stock_levels.py` | Created | Frozen `CatalogStockRow` dataclass (`product_id, product_slug, product_name, product_model, variant_id, color, quantity_on_hand`) + `ListCatalogStockLevelsUseCase(products, stock_levels)` — `execute(below, search)` flattens `list_all()` into rows, attaches product context from the same `Product`/`ProductVariant` objects, clamps `below` with `max(0, below)` (never `max(1, ...)` — D5/D11), AND-filters with a casefolded substring match, sorts ascending with the full tiebreaker tuple. Imports `ProductRepository`/`CatalogStockLevelsReader` ports only (D7) |
| `backend/tests/integration/api/test_admin_stock.py` | Modified | Extended `make_product` with an optional `name` kwarg (backward-compatible — existing callers unaffected, same default). Added 7 new tests under a new `GET /admin/stock` section: no token → `401` + zero repository/reader calls; authenticated response rows carry `product_id`/`product_slug`/`product_name`/`product_model`/`variant_id`/`color`/`quantity_on_hand`; bulk stock reader called exactly once regardless of product/variant count (spy, proves no N+1); omitting both params returns every variant; `?below=0` narrows to zero-quantity rows only; `?search=` narrows by product name; a bulk-read failure (`asyncpg.PostgresConnectionError`) returns `500` with no `_execute_or_raise` involvement |
| `backend/src/gcell/api/admin.py` | Modified | New standalone `AdminCatalogStockRowResponse` (NOT a subclass of `AdminVariantStockResponse` or any `AdminProductList*` model — Pydantic serializes by declared field type, D3/D4) with `.from_domain(CatalogStockRow)`. New `GET /admin/stock` route accepting optional `below: int | None = None` and `search: str | None = None` query params; inside one `pool.acquire()`, constructs `PostgresProductRepository(conn)` and `PostgresStockLevelReader(conn)` bound to the same connection and hands both to `ListCatalogStockLevelsUseCase` — the use case itself calls `list_all()` then `quantities_for_variants()` internally (design.md's Interfaces/Contracts contract: `execute()` takes only `below`/`search`, not pre-fetched data). No `_execute_or_raise` wrapping (D6) — a bulk-read failure propagates naturally to FastAPI's default `500` |

### TDD Cycle Evidence
| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1/1.2 | `test_list_catalog_stock_levels.py` | Unit | N/A (new) | ✅ Written (`ModuleNotFoundError: No module named 'gcell.stock.application.list_catalog_stock_levels'` confirmed) | ✅ Passed (11/11) after one test-data fix (`test_below_and_search_combine_with_and` initially put all 3 variants on one product, so the shared product name matched search for all of them regardless of `below` — split into two products so search/below diverge independently) | ✅ 11 cases covering clamp, both search fields, AND-combine, empty catalog, tie stability, SQL-injection-shaped input | ➖ None needed |
| 2.1/2.2 | `test_admin_stock.py` (extended) | Integration (API) | ✅ 19/19 pre-existing rows in that file, run before edit | ✅ Written (7 failures confirmed: 401-test failed on zero-calls assertion path since route didn't exist yet giving 404 not 401 in one case, 6× `404 != 200`/`500` — route did not exist) | ✅ Passed (26/26 in file) after adding an optional `name` kwarg to the file's existing `make_product` helper (needed for the search-by-name test; default value preserved, verified no existing test's behavior changed) | ✅ 7 new scenarios covering every RED assertion in one pass (auth gate, row shape, single bulk-call, unfiltered, `below`, `search`, 500 propagation) | ➖ None needed |

### Work Unit Evidence
| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest tests/unit/stock/test_list_catalog_stock_levels.py tests/integration/api/test_admin_stock.py -v` → **37 passed** (11 new unit + 26 total in the integration file, 19 pre-existing + 7 new) |
| Runtime harness command/scenario and exact result | N/A — zero new SQL (Decision 4, confirmed in `list_catalog_stock_levels.py`: no `asyncpg`/query string anywhere in the use case). `list_all()`/`quantities_for_variants()` are already DB-tested by `admin-stock-overview`'s `test_admin.py` suite (unchanged, still passing); this route only composes them via monkeypatched-spy adapters, same convention as every other test in `test_admin_stock.py` and `test_admin.py` |
| Rollback boundary | Revert 1 new file (`list_catalog_stock_levels.py`) + 1 new test file (`test_list_catalog_stock_levels.py`) + the `admin.py` diff (1 new import block, 1 new response model, 1 new route — all additive, appended inside the existing "Stock" section comment block, before `AdminVariantStockResponse`) + the `test_admin_stock.py` diff (1 backward-compatible helper signature widening + 7 new test functions, all appended at the end of the file). Every existing `/admin/products*` and `/admin/products/{id}/stock*` route, and every pre-existing test in both files, is untouched and still passing. |

### Full Suite Confirmation
`cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest -q` → **337 passed, 2 warnings** (warnings are pre-existing: a `StarletteDeprecationWarning` about `httpx`/`starlette.testclient`, and a `DecompressionBombWarning` from an existing Pillow test — both unrelated to this change). `tests/architecture/test_domain_boundary.py` explicitly re-run standalone and passes.

`uv run ruff check` on all 4 touched files → clean (2 auto-fixable import-order issues and 1 unused-import fixed during this batch; 1 line-length violation manually shortened).

### Test Summary
- **Total tests written**: 18 new test functions (11 unit + 7 integration)
- **Total tests passing**: 18/18 new, 337/337 full backend suite
- **Layers used**: Unit (11), Integration-API (7)
- **Approval tests** (refactoring): None — no refactoring tasks in this batch
- **Pure functions created**: 0 new standalone pure functions — the clamp/match/sort
  logic lives inside `ListCatalogStockLevelsUseCase.execute`, an async method with I/O
  reader calls, matching the precedent set by `ListVariantStockMovementsUseCase.execute`

### Deviations from Design
1. **Route composition shape**: design.md's prose ("hands both to the use case") is
   ambiguous between "hand the two adapters" and "hand pre-fetched data" — but its own
   Interfaces/Contracts code block is unambiguous: `execute(self, below, search)` takes
   no `products`/`quantities` arguments, so the use case must call `list_all()` and
   `quantities_for_variants()` itself. Implemented accordingly: the route constructs
   `PostgresProductRepository(conn)` and `PostgresStockLevelReader(conn)` and passes
   those adapter instances into `ListCatalogStockLevelsUseCase`'s constructor, then
   awaits `execute()` inside the same `pool.acquire()` block. This matches the
   Interfaces/Contracts section exactly; an earlier draft that pre-fetched data and
   wrapped it in ad-hoc adapter shims was discarded before being tested, since it
   deviated from the locked contract.
2. **Spec.md wording vs. design.md/proposal.md**: `specs/admin-api-access/spec.md`'s
   prose says `below` narrows to rows "strictly less than `below`" and names the query
   param `q`. This contradicts `design.md` Decision 2 (explicitly `<=`, inclusive —
   "Under exclusive `<`, `below=0` would match only negative quantities — empty and
   meaningless, contradicting D11") and the task instructions/D2's Interfaces/Contracts
   code block (`r.quantity_on_hand <= threshold`, param name `search`). Strict `<`
   is also self-contradictory with D11's own requirement that `below=0` must return a
   non-empty "only out-of-stock" result — no quantity is ever `< 0`. Implemented
   `search`/`<=` per design.md and the proposal's locked D2/D11, treating spec.md's
   wording as a drafting artifact (likely copy-pasted from the movements `limit`
   spec) rather than a locked decision — `sdd-verify` should reconcile spec.md's
   prose to match design.md before archive.

### Issues Found
None in the implementation. `make_product`'s pre-existing signature in
`test_admin_stock.py` didn't accept a `name` override, needed for the new
search-by-product-name test — widened with a backward-compatible optional kwarg
(default unchanged, verified no existing test's assertions changed).

### Workload / PR Boundary
- Mode: chained PR slice (2 chained PRs — backend first, frontend second — per this
  session's confirmed delivery decision; tasks.md's `Suggested Work Units` table,
  Unit 1 / PR 1)
- Current work unit: Unit 1 / PR 1 (backend: use case + route + response model + tests)
- Boundary: starts from a clean backend (no `list_catalog_stock_levels.py` module
  existed, no `/admin/stock` route existed) and ends with the GET catalog-triage
  endpoint fully implemented, tested (unit + integration), linted, and passing against
  the full suite. Phase 3-5 (frontend proxy, page, nav link) are untouched and will
  consume this endpoint in PR 2; PR 1's endpoint stays valid and usable standalone
  (via direct API call) regardless of PR 2's timing.
- Estimated review budget impact: within the forecast's backend estimate
  (~450-600 lines); this is a self-contained, independently revertible PR 1

### Status
4/13 tasks complete (Phase 1-2 done; Phase 3-6 remain). Ready for the next apply batch
(frontend: Phase 3 proxy, Phase 4 page, Phase 5 nav link, Phase 6 full verification)
once PR 1 is reviewed/merged, or for `sdd-verify` to check this batch's backend slice
in isolation first.
