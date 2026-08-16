## Exploration: admin-stock-page

### Current State (confirmed by reading source)

**Reusable bulk stock port** — `backend/src/gcell/stock/application/catalog_stock_levels_reader.py`:
```python
class CatalogStockLevelsReader(Protocol):
    async def quantities_for_variants(self, variant_ids: Sequence[UUID]) -> dict[UUID, int]: ...
```
Totality contract: every requested id is always a key, `0` for zero-movement variants. Implemented identically (lockstep) on `PostgresStockLevelReader` (`backend/src/gcell/stock/infrastructure/postgres_stock_level_reader.py`, one `ANY($1::uuid[])` query against the `variant_stock_levels` view) and `InMemoryStockLevelReader` (`backend/src/gcell/stock/infrastructure/in_memory_stock_level_reader.py`). Neither needs changes to support a new page.

**Existing composition precedent** — `backend/src/gcell/api/admin.py:220-235`, `list_admin_products`:
```python
async with pool.acquire() as conn:
    products = await PostgresProductRepository(conn).list_all()
    variant_ids = [variant.id for product in products for variant in product.variants]
    quantities = await PostgresStockLevelReader(conn).quantities_for_variants(variant_ids)
return [AdminProductListItemResponse.from_domain(product, quantities) for product in products]
```
No `_execute_or_raise` wrapping — a bulk-read failure falls through to FastAPI's default 500 (design.md's D6 in the prior change). This is the exact pattern a new route should mirror.

**Frontend today** — `frontend/src/app/(admin)/admin/products/page.tsx` is a Server Component with no `searchParams`, fetching `app/api/admin/products` (cookie forwarded by hand since server-side `fetch` doesn't auto-carry cookies), rendering one row per product with a nested variant list; zero-stock variants get `text-destructive` styling + "Out of stock" label — this is the visual convention to reuse for "critical" rows. `frontend/src/app/api/admin/products/route.ts` is a thin GET-only Route Handler built on the shared `adminBackendFetch(path, init)` helper (`frontend/src/lib/admin/backend-fetch.ts`) — session-gates via `getClaims()`, then relays with a Bearer token. `path` is a plain string, so query params (`/admin/stock?below=5`) pass straight through with zero extra plumbing.

Grep confirmed: **no admin page anywhere uses `searchParams`** today. The closest analog is `ListVariantStockMovementsUseCase` (`backend/src/gcell/stock/application/list_variant_stock_movements.py`), which clamps `limit`/`before_id` in the use case itself (`max(1, min(limit, 100))`), not via FastAPI `Query()` validation — a pattern worth reusing for a new threshold/sort param.

`Product`/`ProductVariant` domain (`backend/src/gcell/products/domain/product.py`): a variant only has `id, color, price, cost` — no back-reference to its product. A flat per-variant `/admin/stock` view needs the route to attach product context (name/model/slug) to each row.

### The Gap

Two deferred items from `admin-stock-overview`'s Out-of-Scope table: a dedicated `/admin/stock` route/page, and low-stock threshold/sort/filter (genuinely new frontend infra — no `searchParams` pattern exists yet).

### Options

| # | Approach | Backend | Frontend | Tradeoffs |
|---|----------|---------|----------|-----------|
| (a) | Sort-only on existing list | Add optional sort to `list_admin_products` (or sort client-side) | Add a `?sort=` link on `/admin/products`, no new page | Cheapest, zero new routes. But doesn't satisfy "dedicated page," stays grouped-by-product — harder to triage many low-stock variants scattered across products. Doesn't really unblock the deferred item as named. |
| (b) | Dedicated `/admin/stock` page, flat per-variant, sort + threshold | NEW `GET /admin/stock` route reusing `list_all()` + `quantities_for_variants()` exactly like `list_admin_products`, but flattened to one row per variant with product context attached; NEW response model | NEW `frontend/src/app/api/admin/stock/route.ts` proxy (same `adminBackendFetch` pattern); NEW `frontend/src/app/(admin)/admin/stock/page.tsx` with `searchParams`-driven sort (default quantity ascending) + `?below=N` threshold filter | Real new infra (first `searchParams` admin page) but bounded — no new backend port, no schema/migration. Matches what was explicitly deferred. |
| (c) | (b) + zero-stock "critical" styling | same as (b) | same as (b), reuse the existing `isZero` destructive-text convention from `admin/products/page.tsx` for `quantity_on_hand === 0` rows | Same bounded surface as (b), plus visual consistency with the already-shipped zero-stock convention. |

**Recommendation: (c).** It satisfies both deferred items exactly as named in the prior proposal, requires zero backend port/adapter changes (the bulk read and totality contract are already correct and reusable), and reuses an existing UI convention rather than inventing a new one. New surface is bounded to one backend route + one response model + one frontend proxy route + one new page.

### Hexagonal Constraints

Same as the prior change: dependency direction `stock -> products` is convention/docstring-only, not test-enforced (`test_domain_boundary.py` only bans framework imports in `domain/`, it does not check direction) — a new route should still compose in `api/admin.py` (never inside `products/`) to keep the convention consistent, but nothing in CI will catch a violation.

### Proxy Route Needed

Yes — unlike `admin-stock-overview` (which added a field to an existing `GET /admin/products` response, D2: "no new endpoint, no new frontend proxy route"), this is a genuinely new backend endpoint (`GET /admin/stock`), so it needs its own new Next.js proxy route (`frontend/src/app/api/admin/stock/route.ts`) following the exact `adminBackendFetch` pattern already used for products.

### Open Questions for Proposal

1. Threshold semantics: fixed default vs. user-configurable `?below=N`, and what default value.
2. Sort scope: quantity-ascending only (fixed), or a general `?sort=` param with multiple columns.
3. Response model shape: extend/reuse `AdminProductListVariantResponse` fields plus product name/slug, or define a fresh flat model.
4. Pagination: `list_all()` is unpaginated today (prior change flagged this as a low-likelihood risk for large catalogs) — likely fine to leave unpaginated for MVP, but worth an explicit decision.
5. Hexagonal direction (convention-only, not test-enforced) carries over verbatim and should be restated rather than reopened.

### Ready for Proposal

Yes.
