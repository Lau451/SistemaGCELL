# Exploration: Admin stock movement history

## Current State

`admin-stock-management` (archived at `openspec/changes/archive/2026-08-15-admin-stock-management/`) shipped record-movement and current-quantity-only read. Its `design.md` explicitly lists "Movement history listing" under **Out of Scope** as a deferred follow-up — this change is exactly that follow-up.

**Domain** — `backend/src/gcell/stock/domain/stock_movement.py`: frozen `StockMovement` dataclass, `MovementType` StrEnum (restock/sale/return/breakage/adjustment), sign-per-type invariant in `__post_init__`.

**Ports** — `backend/src/gcell/stock/application/`:
- `repository.py` — `StockMovementRepository` Protocol has **exactly one** method: `record(movement) -> None`. Docstring explicitly frames this as a port-SHAPE fact (append-only). No listing method.
- `stock_level_reader.py` — `StockLevelReader` Protocol has **exactly one** method: `quantity_on_hand(variant_id) -> int`. Docstring: "a bulk read (`dict[UUID, int]`) is explicitly out of scope" — no listing/paging port either.

Confirms the suspicion directly: **history needs a new port + Postgres adapter query** — no existing port/use case lists or paginates movements.

**Infra**: `PostgresStockMovementRepository.record()` only INSERTs. `PostgresStockLevelReader.quantity_on_hand()` selects the `variant_stock_levels` view (SUM per variant, coalesced to 0). Neither has a SELECT-many.

**Schema** (`supabase/migrations/20260810000453_stock_movements_ledger.sql`):
```sql
stock_movements(
  id bigint generated always as identity primary key,
  variant_id uuid not null references product_variants(id) on delete restrict,
  movement_type text not null,
  quantity_delta integer not null,
  reason text,
  created_at timestamptz not null default now(),
  ...check constraints for type/sign...
)
```
Only index: `stock_movements_variant_id_covering_idx ON stock_movements(variant_id) INCLUDE (quantity_delta)` — SUM-optimized, **not** `ORDER BY created_at`-friendly. Since `id` is a monotonically-increasing identity column on an append-only, trigger-protected table, `id`-order == chronological order — so keyset pagination by `id DESC` avoids needing a new index at all.

**No pagination pattern (limit/offset/cursor) exists anywhere in this backend today** — this change would set a first precedent.

**Route pattern to mirror** (`backend/src/gcell/api/admin.py`):
- Router-level `Depends(verify_admin_jwt)` gates all `/admin/*` routes — a history route needs no separate auth.
- `GET /admin/products/{product_id}/stock` is the read precedent: composes `PostgresProductRepository.get_by_id` + a stock port **directly in the route handler**, no use case (design.md Decision 2: "a use case here would own no decision beyond a `for` loop").
- The write-side IDOR precedent is `RecordVariantStockMovementUseCase` (`backend/src/gcell/stock/application/record_variant_stock_movement.py`): fetches product, checks `variant_id` is in `product.variants`, raises `VariantNotFoundError` (never 403) before delegating. `_execute_or_raise` already maps `ProductNotFoundError`/`VariantNotFoundError` → 404 uniformly.
- Open design question for proposal: does a history route's IDOR-guard-plus-pagination logic still qualify as "no decision beyond a for loop" (→ compose directly, Decision-2 style) or warrant a dedicated use case mirroring `RecordVariantStockMovementUseCase` (more testable, DRY-er)?

**Frontend**:
- `frontend/src/app/(admin)/admin/products/stock-manager.tsx` currently renders only current-quantity + record form; `initialStock` prop has no history. Convention: server-fetched prop is the single rendered source of truth (no local `useState` copy), refreshed via `router.refresh()` after a successful submit.
- `frontend/src/app/(admin)/admin/products/[id]/page.tsx` fetches `/api/admin/products/{id}/stock` via a same-origin, cookie-forwarded proxy fetch and passes it down as `initialStock`. A history fetch needs an analogous fetch fn + a new proxy route.
- `frontend/src/app/api/admin/products/[id]/stock/route.ts` is the exact proxy pattern to mirror (`adminBackendFetch` relay, `NO_STORE_HEADERS`, 401/502 handling).
- No pagination UI pattern exists in the frontend admin area yet either (image-manager.tsx and stock-manager.tsx both render short, unpaginated lists).

**Tests**: `backend/tests/integration/api/test_admin_stock.py` (TestClient + forged JWT + monkeypatched adapters) and `backend/tests/integration/db/test_stock_movement_repository.py` (`db_conn` rollback-isolated real Postgres) show the exact conventions a history test suite would extend.

## Affected Areas
- `backend/src/gcell/stock/application/repository.py` — new port/method needed (currently `record`-only)
- `backend/src/gcell/stock/infrastructure/postgres_stock_movement_repository.py` — new SELECT query/method
- `supabase/migrations/` — possibly a new index migration, depending on pagination-order decision
- `backend/src/gcell/api/admin.py` — new GET route + Pydantic response model
- `backend/src/gcell/stock/application/` — possibly a new use case (open question)
- `frontend/src/app/api/admin/products/[id]/.../route.ts` — new proxy route
- `frontend/src/app/(admin)/admin/products/[id]/page.tsx` — new fetch fn + prop wiring
- `frontend/src/app/(admin)/admin/products/stock-manager.tsx` (or new sibling component) — integration point for history table
- `backend/tests/integration/api/test_admin_stock.py`, `backend/tests/integration/db/test_stock_movement_repository.py` — extend

## Approaches

1. **New port + adapter method, route composed directly in admin.py (Decision-2 precedent)** — id-order (`ORDER BY id DESC LIMIT`) keyset pagination, no new index needed.
   - Pros: minimal new surface, follows the just-established Decision-2 precedent, no migration required.
   - Cons: IDOR ownership check duplicated inline in the route unless factored out.
   - Effort: Low–Medium.

2. **Dedicated use case (`ListVariantStockMovementsUseCase`) mirroring `RecordVariantStockMovementUseCase`'s IDOR-guard-plus-delegate shape.**
   - Pros: consistent with the write-side precedent, keeps `_execute_or_raise`'s existing 404 mapping working unchanged, easier to unit-test the guard.
   - Cons: more code for what might still be "no decision beyond a for loop" per Decision 2's own reasoning — a genuine judgment call.
   - Effort: Medium.

3. **Route shape: per-variant-only vs per-product rollup** (not mutually exclusive with 1/2). Per-variant-only mirrors the existing POST path (`/admin/products/{product_id}/variants/{variant_id}/stock/movements`, GET added). Per-product rollup (`/admin/products/{product_id}/stock/movements`, all variants) needs cross-variant pagination — meaningfully more complex, and risks blurring into the explicitly out-of-scope cross-product overview feature.
   - Effort: Low (per-variant) vs Medium–High (rollup).

## Recommendation

Approach 2 + per-variant-only route for MVP, using `id DESC` keyset pagination to avoid a new migration. This stays consistent with the codebase's established write-side IDOR pattern, keeps the guard testable/DRY against the existing use case, and avoids cross-variant pagination complexity that would blur into the explicitly out-of-scope cross-product overview feature. The proposal phase must explicitly decide: (a) route shape, (b) pagination mechanism and param names/default/max page size, (c) whether "resulting balance after this movement" ships in MVP (would need a SQL window function or be computed client-side/omitted).

## Risks
- No existing pagination pattern anywhere in this backend — this change sets a precedent that the next two planned follow-ups (cross-product overview, initial-stock seeding) will likely copy; the design phase should be deliberate.
- If `created_at`-ordered pagination is chosen instead of PK/id-order, a new index migration is required — must be flagged explicitly, not discovered mid-implementation.
- "Resulting balance after this movement" is unresolved — needs a SQL window function or client-side computation; affects pagination design cost.
- A per-product rollup route (Approach 3, cross-variant) risks blurring scope into the explicitly out-of-scope cross-product overview feature if not bounded carefully.

## Explicitly Out of Scope
- Cross-product stock overview (separate planned SDD change).
- Initial-stock seeding UX (separate planned SDD change).
