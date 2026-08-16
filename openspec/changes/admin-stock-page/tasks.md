# Tasks: Admin Stock Page

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1050-1250 (backend ~450-600, frontend ~590-650) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (backend: use case + route + response model + tests) → PR 2 (frontend: proxy + page + nav link + tests) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

Rationale: this is a brand-new endpoint (not a field add like `admin-stock-overview`,
~260-340 total/Low), with a NEW use case owning three testable rules (clamp,
case-insensitive AND-matching, total sort order incl. tie stability), a NEW
standalone response model, a NEW allowlisted proxy, and the FIRST admin page
reading `searchParams` (new convention to establish + two distinct empty-state
strings + row-link). Comparable in shape to `admin-stock-movement-history`
(~950-1250, Medium, chained), but adds search/filter surface that change did
not have. Backend and frontend are independently reviewable, testable
(mocked/spy adapters, no live DB needed — Decision 4: zero new SQL), and
revertible, so the same 2-unit split applies. Chain strategy is left `pending`
per this session's `ask-on-risk` delivery strategy — the orchestrator must ask
the user (stacked-to-main vs feature-branch-chain) before `sdd-apply` starts
either unit.

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | `ListCatalogStockLevelsUseCase` + `AdminCatalogStockRowResponse` + `GET /admin/stock` route + unit/integration tests | PR 1 | `cd backend && uv run pytest tests/unit/stock/test_list_catalog_stock_levels.py tests/integration/api/test_admin_stock.py -v` | N/A — zero new SQL (Decision 4); `list_all()`/`quantities_for_variants()` are already DB-tested by `admin-stock-overview`; this route only composes them via spy adapters | Revert `list_catalog_stock_levels.py` + `admin.py` route/model diff + the two test file diffs; every existing `/admin/products*` and `/admin/products/{id}/stock*` route untouched |
| 2 | Proxy `stock/route.ts`, `stock/page.tsx`, nav link | PR 2 (base = PR 1 branch once merged, or main) | `cd frontend && npm test -- "stock/__tests__/route.test.ts" "admin/stock/page.test.tsx" layout.test.tsx` | `npm run dev` + backend running — manual visit `/admin/stock`, apply `?below=`/search, click a row through to `/admin/products/{id}` | Revert new/modified frontend files; PR 1's endpoint stays valid and unused standalone until this PR lands |

## Phase 1: Backend — Use case (D1-D11, Decisions 1-2)

- [x] 1.1 RED `backend/tests/unit/stock/test_list_catalog_stock_levels.py` (new) — ascending order incl. tie stability (`quantity_on_hand`, then `product_name`, `color`, `variant_id`); `below=0` → only zeros (D11); `below=-5` clamps to `0`, never errors (D5); `below=None` → every row (D1); case-insensitive substring match on product name; on variant color (D8); blank/whitespace-only search ignored (D9); `below`+search combine with AND (D10); empty catalog → `[]`; search `"'; DROP TABLE products;--"` returns `[]`, raises nothing (threat matrix: SQL injection via `search`)
- [x] 1.2 GREEN `backend/src/gcell/stock/application/list_catalog_stock_levels.py` (new) — frozen `CatalogStockRow` dataclass + `ListCatalogStockLevelsUseCase(products, stock_levels)`; `execute(below, search)` per design's Interfaces/Contracts (D7: imports `ProductRepository`/`CatalogStockLevelsReader` ports only)

## Phase 2: Backend — Route + response model (D3, D4, D6, D13; spec: admin-api-access)

- [x] 2.1 RED extend `backend/tests/integration/api/test_admin_stock.py` — no token → `401`, zero `list_all`/bulk-read calls (spec: "Unauthenticated request never reaches the repository"); authenticated, no params → one row per variant carrying `product_id`, product name/slug, quantity, exactly one bulk stock query regardless of variant count (spec: "one row per variant from one bulk query"); `?below=0` treated as literal `0`, never substituted with `1` (spec: "below=0 is accepted and not clamped to 1"); bulk-read failure → framework default `500`, no partial/degraded list, no `_execute_or_raise` (spec: "Bulk stock read failure propagates to a 500"); `?below=-5` behaves identically to `?below=0` (threat matrix: `below` negative clamps)
- [x] 2.2 GREEN `backend/src/gcell/api/admin.py` — add standalone `AdminCatalogStockRowResponse` (never a subclass, D3) + `GET /admin/stock` route: `pool.acquire()` → `PostgresProductRepository.list_all()` + `PostgresStockLevelReader.quantities_for_variants()` (byte-for-byte `list_admin_products` composition, D6: no `_execute_or_raise`) → `ListCatalogStockLevelsUseCase.execute(below, search)` → serialize rows

## Phase 3: Frontend — Proxy (Decision 5)

- [ ] 3.1 RED `frontend/src/app/api/admin/stock/__tests__/route.test.ts` (new) — unauthenticated → `401` before any `fetch`; backend unavailable → `502`; `below`/`search` forwarded into a freshly rebuilt `URLSearchParams`; an injected extra param (e.g. `?below=1&limit=999`) is dropped, never reaches the backend URL (threat matrix: param smuggling through the proxy); `Cache-Control: private, no-store` header present
- [ ] 3.2 GREEN `frontend/src/app/api/admin/stock/route.ts` (new) — `GET(request)`, no `RouteContext` (no dynamic segment); `ALLOWED_QUERY_PARAMS = ["below", "search"]`, allowlist rebuild mirroring the movements proxy idiom, never `url.search` verbatim; `adminBackendFetch("/admin/stock" + query)`

## Phase 4: Frontend — Page (D12, D13, Decisions 6-7)

- [ ] 4.1 RED `frontend/src/app/(admin)/admin/stock/page.test.tsx` (new) — one row rendered per variant; a `0`-quantity row carries `text-destructive` + "Out of stock" (spec: "Zero-Stock Variants Are Visually Distinguished" — triage surface); each row links to `/admin/products/{product_id}` (D13); fetch failure renders `Unable to load stock.`; zero rows with an active filter (`search`/`below` normalized) renders `No variants match your search or filter.`; zero rows with no active filter renders `No variants in the catalog yet.` — both strings distinct (D12); array-valued `?search=a&search=b` collapses to `"a"` (Decision 7)
- [ ] 4.2 GREEN `frontend/src/app/(admin)/admin/stock/page.tsx` (new) — `await searchParams`, `Array.isArray(v) ? v[0] : v` collapse, forward as strings to the proxy (Decision 7); render table with search input + `below` input, row `<Link href={`/admin/products/${row.product_id}`}>`, filter-active detection reusing backend normalization (`search.trim() !== ""`, `below` parses to a number) to pick the empty-state copy (Decision 6)

## Phase 5: Frontend — Nav link

- [ ] 5.1 RED extend `frontend/src/app/(admin)/admin/layout.test.tsx` — a "Stock" link is present with `href="/admin/stock"`
- [ ] 5.2 GREEN `frontend/src/app/(admin)/admin/layout.tsx` — add `<Link href="/admin/stock">Stock</Link>` beside the existing "Products" link

## Phase 6: Verification

- [ ] 6.1 `cd backend && uv run pytest -v` — full suite, confirm `test_admin.py` (list_admin_products), `test_admin_stock.py`'s existing per-product routes, and `test_domain_boundary.py` pass unmodified
- [ ] 6.2 `cd frontend && npm test` — full suite, confirm `admin/products/page.test.tsx`, movements route/proxy tests, and `layout.test.tsx`'s existing assertions pass unmodified
- [ ] 6.3 Confirm zero diff under `supabase/migrations/`, `stock/infrastructure/**`, `products/**`; `stock → products` import direction unchanged (D7, convention only — not CI-enforced)
