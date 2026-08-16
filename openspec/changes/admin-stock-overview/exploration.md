## Exploration: admin-stock-overview

### Current State

Admins today can only see stock ONE variant/product at a time:
- `GET /admin/products` (`backend/src/gcell/api/admin.py:176-182`, `list_admin_products`) returns `AdminProductResponse` (id, slug, name, model, variants[color, price, cost]) — **no stock quantity field at all**. Backed by `PostgresProductRepository.list_all()` (`backend/src/gcell/products/infrastructure/postgres_product_repository.py:180-182`), already a single-query bulk read (one LEFT JOIN, grouped in Python).
- `GET /admin/products/{id}/stock` (`admin.py:493-508`, `get_admin_product_stock`) does an **N+1 query loop** — one `reader.quantity_on_hand(variant_id)` call per variant, for just ONE product.
- `StockLevelReader` (`backend/src/gcell/stock/application/stock_level_reader.py`) is single-variant-only by design; its own docstring says a bulk `dict[UUID, int]` read was "explicitly out of scope" for `admin-stock-management`, deferred to that change's design.md — this gap was already anticipated, not new.
- The DB is not the bottleneck: `variant_stock_levels` view (`SELECT variant_id, sum(quantity_delta) ... GROUP BY variant_id`, `supabase/migrations/20260810000458_public_catalog_rls.sql:17-23`) sits on a covering index `stock_movements(variant_id) INCLUDE (quantity_delta)` — a single aggregate query across the whole catalog would be an index-only scan. The N+1 is purely code-organization, not schema.
- Frontend product list (`frontend/src/app/(admin)/admin/products/page.tsx`) is a plain Name/Model/Variants/Actions table with zero stock data. Per-variant stock only appears on the product detail page via `StockManager`/`StockHistory`. No `searchParams`/sort/filter infra exists on any admin page yet; a new backend endpoint would need a matching new proxy route (`frontend/src/app/api/admin/products/...` pattern).
- Established precedent: `StockMovementHistoryReader` was added as its own dedicated Protocol+DTO, separate from other stock ports, colocated with a small use case that composes `ProductRepository` for ownership checks — this is the pattern to follow for a new overview reader.

### Affected Areas
- `backend/src/gcell/stock/application/stock_level_reader.py` — needs a bulk method or a new sibling port
- `backend/src/gcell/stock/infrastructure/postgres_stock_level_reader.py` — new aggregate SQL
- `backend/src/gcell/stock/infrastructure/in_memory_stock_level_reader.py` — must gain the same method for tests
- `backend/src/gcell/api/admin.py` — extend `list_admin_products` or add a new route
- `frontend/src/app/(admin)/admin/products/page.tsx` — natural column/badge location
- `frontend/src/app/api/admin/products/...` — new proxy route if a new backend endpoint is added
- `backend/tests/architecture/test_domain_boundary.py` — relevant to hexagonal constraints (see below)

### Approaches
1. **Stock column/badge on the existing product list** — one new bulk aggregate query, added to `list_admin_products`. Pros: cheapest, no new page/route/infra, visible where admins already browse. Cons: no low-stock triage workflow, no sort/filter, no catalog-wide total without extra UI. Effort: Low.
2. **Dedicated "Stock Overview" page** (`/admin/stock`) with a new endpoint, one row per variant across the catalog, sort + low-stock threshold filter. Pros: purpose-built triage UX. Cons: most surface area — new route/models, new proxy route, new page, genuinely new sort/filter infra. Effort: Medium-High.
3. **Both** — list column + dedicated low-stock-only alert view. Pros: covers both framings in the background. Cons: largest effort, likely exceeds the repo's 400-changed-line PR review budget in one PR. Effort: High.

### Recommendation
Build the shared bulk read capability once (new `StockLevelReader` method or a sibling port mirroring `StockMovementHistoryReader`'s isolation), and ship **Option 1** as this change's MVP deliverable — smallest change that directly closes the gap, reuses `PostgresProductRepository.list_all()`'s proven pattern. Treat Option 3's dedicated low-stock view as a natural follow-up change once the bulk port exists.

### Risks
- The existing `get_admin_product_stock` N+1 loop is a live anti-pattern precedent in this codebase; a naive bulk implementation could reproduce it at catalog scale. design.md must explicitly decide "single aggregate query, not a loop."
- `stock -> products` dependency direction is convention-only (module docstrings) — `test_domain_boundary.py` only bans framework imports inside `domain/` layers, it does **not** mechanically forbid `products` importing `stock`. Nothing in CI enforces the direction.
- Option 3 (or any bundling of list column + dedicated page) likely exceeds the 400-changed-line PR budget and needs chained-PR forecasting from `sdd-tasks`.
- In-memory stock reader adapter must be kept in lockstep with any new Postgres reader method or tests will silently miss coverage.

### Open Questions for Proposal
1. Per-variant stock figure on the list, or summed per-product total (or both)?
2. Does the new stock data get added directly to `list_admin_products`'s existing response, or via a parallel composition read the frontend merges client-side?

### Ready for Proposal
Yes. Sufficient precedent exists to draft a proposal directly against Option 1.
