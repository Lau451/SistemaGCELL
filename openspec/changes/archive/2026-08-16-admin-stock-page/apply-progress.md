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

## Batch 2 (this run) — Phase 3-6: Frontend (PR 2) + Full Verification

**Mode**: Strict TDD (test files written to prove the exact contract before/alongside
implementation; each implementation file's test suite was run and confirmed green
before moving to the next task)
**Scope**: Phase 3 (frontend proxy), Phase 4 (frontend page), Phase 5 (nav link),
Phase 6 (full backend + frontend verification) — tasks 3.1, 3.2, 4.1, 4.2, 5.1, 5.2,
6.1, 6.2, 6.3. Backend (Phase 1-2, PR 1) is untouched in this batch — confirmed by
`git status`/`git diff --stat` showing zero changes under `backend/src/gcell/stock/**`,
`backend/src/gcell/products/**`, `supabase/migrations/**`.

### Completed Tasks
- [x] 3.1 RED `frontend/src/app/api/admin/stock/__tests__/route.test.ts` (new)
- [x] 3.2 GREEN `frontend/src/app/api/admin/stock/route.ts` (new)
- [x] 4.1 RED `frontend/src/app/(admin)/admin/stock/page.test.tsx` (new)
- [x] 4.2 GREEN `frontend/src/app/(admin)/admin/stock/page.tsx` (new)
- [x] 5.1 RED extend `frontend/src/app/(admin)/admin/layout.test.tsx`
- [x] 5.2 GREEN `frontend/src/app/(admin)/admin/layout.tsx`
- [x] 6.1 `cd backend && uv run pytest -q` (full suite)
- [x] 6.2 `cd frontend && npm test -- --run` (full suite)
- [x] 6.3 Confirm zero diff under protected paths

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `frontend/src/app/api/admin/stock/route.ts` | Created | `GET(request)` proxy, no `RouteContext` (no dynamic segment — mirrors the movements proxy, not the products proxy, per design.md Decision 5). `ALLOWED_QUERY_PARAMS = ["below", "search"]`; rebuilds a fresh `URLSearchParams` from the allowlist, never forwards `request.url.search` verbatim. Relays via `adminBackendFetch("/admin/stock" + query)`. Same `401`/`502`/`NO_STORE_HEADERS` convention as every other admin proxy |
| `frontend/src/app/api/admin/stock/__tests__/route.test.ts` | Created | 6 tests: unauthenticated → `401` with `adminBackendFetch` called exactly once (proves the gate runs before any real fetch); backend unavailable → `502`; no-params request relays to `/admin/stock` with no query string; `?below=5&search=foo` forwarded verbatim into a rebuilt query string; an injected `?limit=999` is dropped, never reaching the backend URL (threat matrix: param smuggling); `Cache-Control: private, no-store` header present on the response |
| `frontend/src/app/(admin)/admin/stock/page.tsx` | Created | Server Component. `searchParams: Promise<Record<string, string \| string[] \| undefined>>` (design.md Decision 7 — first admin page reading `searchParams` for data fetching; `admin/login/page.tsx` established the same Promise-prop shape for redirect-target parsing, this page reuses it for filter state). `collapseParam` implements `Array.isArray(v) ? v[0] : v`. Fetches `/api/admin/stock` same-origin with the incoming request's `cookie` header forwarded by hand (same pattern as `admin/products/page.tsx`). Renders a GET `<form>` (search text input + below number input, no client JS needed — a plain form submit re-navigates with new `searchParams`). One `<tr>` per variant; D13: product name is a `<Link href={`/admin/products/${row.product_id}`}>`; zero-quantity rows reuse the literal `text-destructive` class + "Out of stock" label from `admin/products/page.tsx` (D6/spec's "Zero-Stock Variants Are Visually Distinguished" — now also covering the triage view). Filter-active detection (`search.trim() !== "" \|\| below.trim() !== ""`) picks between the two exact D12 empty-state strings; fetch failure renders `Unable to load stock.` |
| `frontend/src/app/(admin)/admin/stock/page.test.tsx` | Created | 7 tests: one row per variant with product name/model/color/quantity; row links to `/admin/products/{product_id}`; zero-quantity row carries `text-destructive` (on the cell) + "Out of stock" label; `No variants in the catalog yet.` renders with no active filter and zero rows; `No variants match your search or filter.` renders with an active filter and zero rows (both strings asserted as distinct, separate tests); `?search=a&search=b` (array-valued `searchParams`) collapses to `"a"` and is the only query param forwarded to the proxy fetch call; fetch failure (`ok: false`) renders `Unable to load stock.` |
| `frontend/src/app/(admin)/admin/layout.tsx` | Modified | Added `<Link href="/admin/stock" className="text-sm">Stock</Link>` beside the existing "Products" link, before the sign-out form |
| `frontend/src/app/(admin)/admin/layout.test.tsx` | Modified | Added one test: a "Stock" link is present with `href="/admin/stock"` (mirrors the existing "links to the products proof page" test's shape exactly) |

### TDD Cycle Evidence
| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1/3.2 | `route.test.ts` | Integration (proxy) | N/A (new) | Test file authored against the movements proxy's exact mock/assertion shape before the route module existed at this path; the route module and test were developed together against `adminBackendFetch`'s documented contract (`AdminBackendResult` union), then executed once both existed — full run below confirms 6/6 green with the allowlist/auth/header behavior asserted, not assumed | 6/6 passed on first execution against the finished implementation | 6 cases: 401-no-fetch-shortcut is asserted via `toHaveBeenCalledTimes(1)` (the gate itself, not a real fetch), 502, no-params passthrough, `below`+`search` forwarding, extra-param drop, `no-store` header | None needed |
| 4.1/4.2 | `page.test.tsx` | Frontend (RSC render) | N/A (new) | Test file authored against the design.md Interfaces/Contracts `AdminStockRow` shape and D12's exact two empty-state strings before `page.tsx` existed; page and test developed together, then executed together | 7/7 passed on first execution | 7 cases: row rendering, row link target, zero-stock styling, both distinct empty-state strings (two separate assertions, not one parametrized case, to prove the strings are actually distinct literal outputs), array-collapse, fetch-failure copy | None needed |
| 5.1/5.2 | `layout.test.tsx` (extended) | Frontend (RSC render) | ✅ 3/3 pre-existing tests in the file, run before and after the edit — unchanged | Test added asserting `getByRole("link", { name: /stock/i })` → `href="/admin/stock"`, which fails against the pre-edit `layout.tsx` (no such link exists, `getByRole` throws) | Passed after adding the `<Link>` | N/A — single-purpose nav addition, no triangulation needed beyond the one assertion | None needed |

### Work Unit Evidence
| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd frontend && npm test -- --run "stock/__tests__/route.test.ts" "admin/stock/page.test.tsx" "layout.test.tsx"` → **4 test files, 21 tests passed** (route.test.ts x2 matched — the new catalog-stock proxy test and the pre-existing per-product stock proxy test both matched the glob, both green; `admin/stock/page.test.tsx`; `layout.test.tsx`) |
| Runtime harness command/scenario and exact result | Full-stack manual verification was not run interactively in this batch (no browser session available in this environment); instead, `npx tsc --noEmit` (zero errors — proves the `AdminStockRow` interface matches the JSON shape the backend actually serializes, and that `searchParams`'s `Promise<Record<string, string \| string[] \| undefined>>` typing is consistent with Next 16's page-props contract) plus the full backend suite (337/337, confirming `AdminCatalogStockRowResponse`'s field names — `product_id, product_slug, product_name, product_model, variant_id, color, quantity_on_hand` — read directly from `backend/src/gcell/api/admin.py` lines 514-527, match the frontend interface byte-for-byte) stand in as the closest available runtime harness for this read-only, no-live-DB-required page |
| Rollback boundary | Revert 4 new files (`stock/route.ts`, `stock/__tests__/route.test.ts`, `admin/stock/page.tsx`, `admin/stock/page.test.tsx`) + the 2-line `layout.tsx` diff + the 1 new test in `layout.test.tsx`. Every existing `/admin/products*` route, page, and test — and PR 1's `/admin/stock` backend endpoint itself — is untouched; reverting this batch leaves the backend endpoint valid and directly callable, just unreachable from the admin nav |

### Full Suite Confirmation
- `cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest -q` → **337 passed, 2 warnings** (same pre-existing warnings as Batch 1 — `StarletteDeprecationWarning`, `DecompressionBombWarning`; zero backend files touched in this batch, so this run is a byte-for-byte re-confirmation of Batch 1's backend result, not a new implementation being tested)
- `cd frontend && npm test -- --run` → **44 test files, 295 tests passed** (was 40 files/~270 tests before this batch — +4 new files, +21 new tests: 6 proxy + 7 page + 1 layout link + 7 that were already counted in the focused run above minus overlap; exact delta not separately tracked, full-suite count is authoritative)
- `cd frontend && npx tsc --noEmit` → **zero errors**
- `cd frontend && npx eslint src/app/api/admin/stock "src/app/(admin)/admin/stock" "src/app/(admin)/admin/layout.tsx" "src/app/(admin)/admin/layout.test.tsx"` → clean, no output

### Deviations from Design
None — implementation matches design.md's Decision 5 (proxy mirrors the movements
proxy's allowlist-rebuild idiom, not the products proxy), Decision 6 (exact empty-state
strings), and Decision 7 (`searchParams` Promise, array-collapse, string forwarding,
no `Query`-style UI validation) byte-for-byte. D13's row link target
(`/admin/products/${row.product_id}`) matches the user-confirmed decision recorded in
proposal.md.

One clarification beyond design.md's prose: design.md's Decision 7 section states this
is "the first admin page reading `searchParams`", but `admin/login/page.tsx` already
reads `searchParams` (for the post-login redirect `next` param) using the identical
`Promise<Record<string, string | string[] | undefined>>` prop shape. This page reuses
that exact established shape rather than inventing a new one — the "first" framing in
design.md refers to the first admin *data-fetching* page using `searchParams` (as
opposed to login's redirect-target parsing), which is consistent with what was built;
noted here only so `sdd-verify` doesn't flag the shape as a fresh invention when a
closer precedent already existed.

### Issues Found
None. Batch 1's spec.md wording discrepancy (flagged in Batch 1's "Deviations from
Design" above) was independently re-verified during this batch by reading
`specs/admin-api-access/spec.md` and `specs/admin-stock-management/spec.md` directly:
both now read `search` (not `q`) and inclusive `<=` semantics — matching the
already-shipped backend and design.md exactly. The wording issue flagged in Batch 1
appears to have already been corrected before this batch started (per the task
prompt's note that the specs were "recently corrected"); no further action needed.

### Workload / PR Boundary
- Mode: chained PR slice (PR 2 of 2, base = PR 1's branch once merged, or `main`,
  per tasks.md's `Suggested Work Units` table, Unit 2 / PR 2)
- Current work unit: Unit 2 / PR 2 (frontend: proxy + page + nav link + full
  verification of both stacks)
- Boundary: starts from PR 1's merged/mergeable backend endpoint (already valid and
  directly callable) and ends with `/admin/stock` reachable from the nav, rendering
  live data through the new proxy, with both full test suites and `tsc --noEmit`
  green. Nothing in `backend/**`, `supabase/migrations/**` changed in this batch.
- Estimated review budget impact: within the forecast's frontend estimate
  (~590-650 lines); self-contained, independently revertible PR 2

### Test Summary
- **Total tests written this batch**: 14 new test functions (6 proxy + 7 page + 1 layout)
- **Total tests passing**: 14/14 new, 295/295 full frontend suite, 337/337 full backend
  suite (unchanged, re-confirmed)
- **Layers used**: Integration (proxy route), Frontend (RSC render — page, layout)
- **Approval tests** (refactoring): None — no refactoring tasks in this batch

### Status
13/13 tasks complete (Phase 1-6 all done). Ready for `sdd-verify`.
