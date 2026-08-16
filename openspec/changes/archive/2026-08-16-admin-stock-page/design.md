# Design: Admin Stock Page

## Technical Approach

A new `ListCatalogStockLevelsUseCase` (`stock/application/`) owns clamping,
matching and ordering. `GET /admin/stock` in `api/admin.py` composes
`PostgresProductRepository.list_all()` with the EXISTING
`PostgresStockLevelReader.quantities_for_variants()` inside one
`pool.acquire()` — byte-for-byte the `list_admin_products` composition (D6:
no `_execute_or_raise`) — hands both to the use case, and serializes flat
`AdminCatalogStockRowResponse` rows (D4). Frontend adds a param-forwarding
proxy and the first `searchParams` admin page. No new port, no adapter, no
domain, no SQL, no migration.

## Architecture Decisions

### Decision 1: Filtering/sorting lives in a use case, not inline in the route

| Option | Tradeoff | Decision |
|---|---|---|
| Inline in `api/admin.py` | Matches `list_admin_products`, but that route owns no rule beyond a loop. Here the rules (clamp, casefold substring, AND, total sort order) are testable without FastAPI or a DB and would become route-only logic | Rejected |
| `ListCatalogStockLevelsUseCase` in `stock/application/` | Exact `ListVariantStockMovementsUseCase` precedent — that use case owns its clamp for the same reason. Imports `ProductRepository`/`CatalogStockLevelsReader` ports only, so direction stays `stock → products` (D7) | **Chosen** |

D6 still holds: the use case raises no application exception, so there is
nothing for `_execute_or_raise` to map, and wrapping would turn a driver
failure into a 422 (prior design's Decision 4). Contrast
`get_admin_variant_stock_movement_history`, which wraps only because its use
case raises `Product/VariantNotFoundError`.

### Decision 2: `below` is inclusive (`<=`), clamped `max(0, ...)`

D11 locks `?below=0` as "only out-of-stock". Under exclusive `<`, `below=0`
would match only negative quantities — empty and meaningless, contradicting
D11. So the predicate is `quantity_on_hand <= below`; `?below=5` means "5 or
fewer". Clamp is `max(0, below)` (D5/D11 — never `max(1, ...)`), so
`?below=-5` degrades to `0`, never a 400/422. Annotation stays
`below: int | None = None`, matching `limit: int = 20` on the movements
route: FastAPI's type coercion is not `Query(ge=0)` validation, and D5
governs range, not parseability.

### Decision 3: New flat model, never a subclass

`AdminCatalogStockRowResponse` is standalone. Subclassing
`AdminProductVariantResponse` to bolt on product context is rejected for the
reason already recorded in `admin-stock-overview`'s design (Decision 3):
Pydantic serializes by *declared* field type, so a subclass silently drops
the extra keys wherever the parent is the annotation. `AdminProductResponse`,
`AdminProductListItemResponse` and `AdminProductListVariantResponse` are
untouched (D4).

### Decision 4: Search matches in Python; zero new SQL

`list_all()` already loads the whole catalog unconditionally, so it — not the
filter — is the scaling ceiling (accepted, Out of Scope). Pushing search into
SQL would need a new repository method inside `products/**`, which this
change forbids. Consequence: no user-controlled string ever reaches a query;
the only SQL executed is the two existing pre-parameterized statements.

### Decision 5: The proxy mirrors the movements proxy, not the products proxy

`api/admin/products/route.ts`'s `GET()` takes no argument, so it cannot read
query params. The precedent that *can* is
`api/admin/products/[id]/variants/[variantId]/stock/movements/route.ts`:
`GET(request: Request)`, rebuilding an allowlisted `URLSearchParams` rather
than forwarding `new URL(request.url).search` verbatim. The new proxy copies
that idiom with `ALLOWED_QUERY_PARAMS = ["below", "search"]`, and has no
`RouteContext` (no dynamic segment). This is a deliberate deviation from the
products proxy, not an invention.

### Decision 6: Empty state disambiguated from active filters, not an envelope

The response stays a bare list (like `list_admin_products`). D1 makes an
unfiltered result total, so "empty result + no active filter" *is* an empty
catalog; "empty result + active filter" is a miss. Filter-active uses the
same normalization as the backend (`search.trim() !== ""`, `below` parses to
a number), so blank `?search=` never triggers the wrong copy. Exact strings:

| Case | Copy |
|---|---|
| Fetch failed | `Unable to load stock.` (mirrors "Unable to load products.") |
| Filter active, 0 rows | `No variants match your search or filter.` |
| No filter, 0 rows | `No variants in the catalog yet.` |

### Decision 7: `searchParams` convention (first admin page — reuse this)

Next 16 hands `searchParams` as a **Promise**; repeated params arrive as an
array. Convention for every future admin page: `await` it, collapse with
`Array.isArray(v) ? v[0] : v`, normalize/validate in the page, forward as
strings, and let the backend clamp. Never `Query`-style validation in the UI.

## Data Flow

    page.tsx (await searchParams) ─fetch─▶ /api/admin/stock?below&search
                                                │ allowlist rebuild
                                                │ adminBackendFetch
                                                ▼
    GET /admin/stock ── pool.acquire() ─┬─ PostgresProductRepository.list_all()
                                        └─ quantities_for_variants([all ids])
                                              └─ 1 query: variant_stock_levels
                     ▼
    ListCatalogStockLevelsUseCase.execute(below, search)
      flatten → attach product ctx → clamp+AND filter → sort asc
                     ▼
    list[AdminCatalogStockRowResponse]

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/src/gcell/stock/application/list_catalog_stock_levels.py` | Create | `CatalogStockRow` + `ListCatalogStockLevelsUseCase` (Decision 1) |
| `backend/src/gcell/api/admin.py` | Modify | `AdminCatalogStockRowResponse` + `GET /admin/stock` route |
| `backend/tests/unit/stock/test_list_catalog_stock_levels.py` | Create | Clamp/match/sort rules |
| `backend/tests/integration/api/test_admin_stock.py` | Modify | Route wiring, params, single bulk read, 500 propagation |
| `frontend/src/app/api/admin/stock/route.ts` | Create | Allowlisted param-forwarding proxy (Decision 5) |
| `frontend/src/app/api/admin/stock/__tests__/route.test.ts` | Create | Auth gate, allowlist, relay |
| `frontend/src/app/(admin)/admin/stock/page.tsx` | Create | `searchParams` Server Component (Decision 7) |
| `frontend/src/app/(admin)/admin/stock/page.test.tsx` | Create | Rows, zero-stock, both empty states |
| `frontend/src/app/(admin)/admin/layout.tsx` (+ `layout.test.tsx`) | Modify | "Stock" nav link beside "Products" |
| `stock/infrastructure/**`, `products/**`, `supabase/migrations/**` | Unchanged | Verified |

## Interfaces / Contracts

```python
@dataclass(frozen=True)
class CatalogStockRow:
    product_id: UUID; product_slug: str; product_name: str
    product_model: str; variant_id: UUID; color: str; quantity_on_hand: int

@dataclass
class ListCatalogStockLevelsUseCase:
    products: ProductRepository
    stock_levels: CatalogStockLevelsReader

    async def execute(
        self, below: int | None = None, search: str | None = None
    ) -> list[CatalogStockRow]: ...
```

```python
# inside execute -- the three rules, verbatim intent
term = (search or "").strip().casefold()          # blank == no search (D8/D9)
threshold = None if below is None else max(0, below)   # D5/D11, never max(1, ..)
rows = [r for r in rows                                # AND (D10)
        if (threshold is None or r.quantity_on_hand <= threshold)
        and (not term or term in r.product_name.casefold()
                      or term in r.color.casefold())]
rows.sort(key=lambda r: (r.quantity_on_hand, r.product_name.casefold(),
                         r.color.casefold(), str(r.variant_id)))  # total order
```

`str(variant_id)` is the final tiebreaker so ties (many `0` rows) are stable
across requests without relying on `list_all()`'s ordering.

```ts
interface AdminStockRow { product_id: string; product_slug: string;
  product_name: string; product_model: string; variant_id: string;
  color: string; quantity_on_hand: number }
```

Zero rows reuse the literal existing convention from
`admin/products/page.tsx`: `className="text-destructive"` plus the label
`Out of stock`. No new convention.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit (use case) | Ascending order incl. tie stability; `below=0` → only zeros; `below=-5` clamps to `0`; `below=None` → all (D1); case-insensitive substring on name AND on color; blank/whitespace search ignored; `below`+search AND-combine; empty catalog → `[]` | `InMemoryProductRepository` + `InMemoryStockLevelReader` |
| Integration (api) | Flat rows carry product name/slug/model; reader called **exactly once** for N products; `?below`/`?search` reach the use case; unfiltered returns every variant; bulk-read failure → 500, no `_execute_or_raise` (D6) | `test_admin_stock.py`, spy adapter + `_FakePool` precedent |
| Integration (proxy) | Unauthenticated → 401 before `fetch`; backend down → 502; `below`/`search` forwarded; **unknown param dropped**; `no-store` header | Extend the products/movements route-test pattern |
| Frontend (page) | One row per variant; `0` → `text-destructive` + "Out of stock"; both empty-state strings distinct; array-valued `?search=a&search=b` collapses to first | `page.test.tsx`, mocked fetch |
| Frontend (layout) | "Stock" link present, `href="/admin/stock"` | Extend `layout.test.tsx` |

## Threat Matrix

Reference rows — all `N/A`: **Documentation-like paths** N/A (no file
classification or execution); **Git repository selection**, **Commit state**,
**Push state**, **PR commands** N/A (no shell, subprocess, VCS or PR
automation anywhere in this change).

Change-specific rows — `search`/`below` are the first NEW user-controlled
input in this line of work (the prior change had none), so these ARE
applicable:

| Vector | Design response | Planned RED test |
|---|---|---|
| SQL injection via `search` | The string never reaches SQL (Decision 4); matching is Python `in` over already-fetched rows. The only statements are the existing `$1`-bound ones. If a future version pushes search down, it MUST be `ILIKE $n` with a bound param — **never** f-string/`%`-formatted SQL | Use-case test with `"'; DROP TABLE products;--"` returns `[]`, raises nothing |
| Param smuggling through the proxy | Allowlist rebuild, never `url.search` verbatim (Decision 5) | Proxy test: `?below=1&limit=999` forwards only `below` |
| `below` non-integer / negative | FastAPI coerces (422 on garbage, same as `limit`); negatives clamp to `0`, never an error | Route test `?below=-5` ≡ `?below=0` |
| Auth | Router-level `Depends(verify_admin_jwt)` + `adminBackendFetch`'s `getClaims()` gate — both reused unchanged, no new surface | Route test: no token → 401, no DB touched |

No write surface, no schema change, no new dependency, read-only end to end.

## Migration / Rollout

No migration required. No schema, view, index, trigger, feature flag or
dependency change. Single-commit revert removes the route, use case, proxy,
page and nav link; `/admin/products` is untouched.

## Open Questions

None. Row affordance was confirmed by the user on 2026-08-16 via
AskUserQuestion and is now locked as proposal.md D13: each row links to
`/admin/products/{product_id}` — the triage-then-act flow the page exists for.
`product_slug` stays in the contract but is not needed by the link itself
(`product_id` is what `/admin/products/{id}` expects); it remains available
for a future breadcrumb/title without a contract change.
