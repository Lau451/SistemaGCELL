# Exploration: Admin stock management

Expose the existing `stock/` domain through `/admin` API endpoints and an admin UI to
record restock/sale/return/breakage/adjustment movements and view current per-variant
stock.

## Current State

`backend/src/gcell/stock/` is fully implemented at domain/application/infrastructure
layers but has zero wiring into the API:

- `domain/stock_movement.py` — `MovementType` StrEnum (restock/sale/return/breakage/adjustment);
  frozen `StockMovement` dataclass validating non-zero delta, sign-per-type, non-blank reason.
- `application/repository.py` — `StockMovementRepository` Protocol with exactly one method:
  `record(movement) -> None`. No update/delete — append-only is a port-shape fact.
- `application/stock_level_reader.py` — `StockLevelReader` Protocol, exactly one method:
  `quantity_on_hand(variant_id) -> int`. Docstring explicitly states bulk read
  (`dict[UUID, int]`) is **out of scope** — no list/bulk port exists today.
- `application/record_stock_movement.py` — `RecordStockMovementUseCase(repository)`.
  `async execute(variant_id: UUID, movement_type: str, quantity_delta: int, reason: str | None = None) -> StockMovement`.
  Takes `movement_type` as a plain `str` specifically so an admin route can hand over
  untyped input; resolves to `MovementType` and raises `ValueError` on an unknown type
  before any persistence. This is the exact use case the new admin "record movement"
  route must call.
- `application/register_stocked_product.py` — `RegisterStockedProductUseCase(products, movements)`.
  `async execute(product, initial_movements: Sequence[StockMovement] = ())`. This is
  **not** a duplicate of `record_stock_movement` — it's a cross-domain composition-root
  use case meant to atomically create a product+variants AND seed initial stock movements
  in one call (needs a shared-connection `transaction()` scope, since it owns no
  transaction itself). Confirmed via grep of `backend/src/`: this use case is never
  invoked anywhere outside its own module — only referenced in a docstring comment and
  its own tests. `create_admin_product` in `admin.py` calls plain `CreateProductUseCase`,
  which does not seed stock. So today, a newly created variant has zero stock (via
  `COALESCE(quantity_on_hand, 0)`) until an admin manually records a restock movement.
- No read/list port exists for movement **history** — only current-quantity read. Showing
  history in the admin UI would require a new port/use case (extending
  `StockMovementRepository` itself would violate its write-only port-shape invariant).
- Infra adapters: `PostgresStockMovementRepository`/`PostgresStockLevelReader` take
  `asyncpg.Connection` (not `Pool`) — same pattern as `PostgresProductRepository`;
  matching in-memory adapters exist for tests.
- DB (already live, per `supabase/migrations/20260810000453_stock_movements_ledger.sql`
  and `20260810000458_public_catalog_rls.sql`): `stock_movements` is append-only via a
  `BEFORE UPDATE OR DELETE` trigger; `variant_stock_levels` view (`SUM(quantity_delta)`
  per variant, internal-only, no anon/authenticated grant); `catalog_variants` view
  derives the public `in_stock` boolean via `COALESCE(sl.quantity_on_hand, 0) > 0`. RLS:
  base tables locked down, only `service_role` has `SELECT, INSERT` on `stock_movements`
  (never `UPDATE`/`DELETE`). Confirmed: no backend test anywhere exercises the `anon`
  role (grep for "anon" across `backend/tests` returned zero files) — RLS is applied at
  the DB and covered only by spec prose, not integration-tested against real
  anon/service_role Postgres roles. This is a pre-existing gap from earlier changes
  (`supabase-schema`, `public-catalog-screens`), not something this change necessarily
  must fix.

`backend/src/gcell/api/admin.py` (390 lines, fully read) has zero stock imports/routes.
Established conventions the new routes must replicate exactly:

- Router-level `Depends(verify_admin_jwt)` — every route inherits `401` automatically.
- `_execute_or_raise[T](operation)` — central exception→HTTP mapping: `ValueError`/`TypeError`
  → 422, `*NotFoundError` → 404 `"not_found"`, `DuplicateProductSlugError` → 409,
  `ObjectStorageError` → 502. `UnknownVariantError` (stock's own FK-violation translation,
  raised by `PostgresStockMovementRepository.record` on `stock_movements_variant_id_fkey`)
  is not yet in this except list — it must be added, mapped to 404 `"not_found"` (same
  IDOR-safe treatment as `ProductNotFoundError`/`VariantNotFoundError`).
- Pydantic response models with `from_domain` classmethods; write-request bodies use
  `ConfigDict(extra="forbid")`.
- `Annotated[asyncpg.Pool, Depends(require_db_pool)]` + `async with pool.acquire() as conn:`
  per route — never a bare `Pool` handed to a repository/use case.
- Existing nesting precedent: `/admin/products/{product_id}/images...` — new stock routes
  would naturally nest as `/admin/products/{product_id}/variants/{variant_id}/stock`.

Frontend admin conventions (already used twice — `admin-product-crud`, `admin-product-images`):

- `frontend/src/lib/admin/backend-fetch.ts` — `adminBackendFetch(path, {method, body})`:
  session-gates via `getClaims()`, relays Bearer token from `getSession()`, JSON-stringifies
  unless `body` is `FormData`, special-cases `204`. Fully reusable for stock with zero changes.
- `frontend/src/app/(admin)/admin/products/actions.ts` — `"use server"` Server Actions per
  write op, all following gate → relay → `revalidatePath` → redirect-or-return-error. A new
  `recordStockMovementAction` follows this exact shape.
- `frontend/src/app/api/admin/products/[id]/...route.ts` — GET-only Route Handler proxies
  (cookie-forwarded, same-origin) feed Server Component reads; writes never go through
  Route Handlers (CSRF rationale documented in `actions.ts`'s header comment).
- `[id]/page.tsx` — Server Component composing `ProductForm` + `ImageManager` (client
  component), each fed via a dedicated proxy route with `initialX` props, mutated via
  Server Actions + `router.refresh()` (server is the single source of truth post-mutation,
  no client optimistic state). A `StockManager`-shaped client component would slot in
  exactly like `ImageManager` did.
- Confirmed: zero references to "stock" anywhere under `frontend/src/app/(admin)`.
- Money-precision discipline (verbatim-string relay, never `parseFloat`/`Number()`) is
  specific to `price`/`cost` (`Decimal`); `quantity_delta` is a plain integer, so `Number()`
  coercion is safe here — worth stating explicitly in design so it isn't cargo-culted into
  an unnecessary string-relay for quantity.

## Affected Areas

- `backend/src/gcell/api/admin.py` — add stock routes, response models, and an
  `UnknownVariantError → 404` mapping in `_execute_or_raise`
- `backend/tests/integration/api/test_admin_stock.py` (new) — mirrors `test_admin_images.py`'s
  structure
- `frontend/src/app/(admin)/admin/products/actions.ts` — add `recordStockMovementAction`
- `frontend/src/app/(admin)/admin/products/[id]/page.tsx` — wire a new stock component
- `frontend/src/app/(admin)/admin/products/stock-manager.tsx` (new)
- `frontend/src/app/api/admin/products/[id]/stock/route.ts` (new GET proxy)
- No changes needed to `stock/` domain/application/infrastructure — pure reuse of existing
  use cases/ports — unless movement history is put in scope (needs a new read port)
- No new Supabase migration — schema, ledger trigger, and RLS are already complete and live

## Approaches

### 1. Embedded, record + current-stock only (no history, no create-time seeding)

`StockManager` client component added to the existing `[id]/page.tsx` alongside
`ProductForm`/`ImageManager`; backend exposes a record-movement write route and a
per-variant (or per-product, looping `quantity_on_hand`) current-stock read route.

- Pros: lowest complexity; reuses 100% of existing use cases/ports/RLS with zero domain
  changes; mirrors the two prior admin-panel precedents file-for-file; per-product variant
  counts are small, so N calls to `quantity_on_hand` is fine without touching the
  bulk-read-is-out-of-scope constraint.
- Cons: no audit trail visible in the UI (movements are recorded but not listed back); new
  products still start at 0 stock until a manual restock.
- Effort: Low–Medium

### 2. Add movement history + a dedicated cross-product `/admin/stock` overview screen

New read port/use case for listing movement rows, plus a bulk-stock-read capability for a
cross-product table.

- Pros: real inventory-ops visibility (audit trail, low-stock overview across all products).
- Cons: requires new backend port/use-case design (not just route wiring) since neither
  history listing nor bulk stock read exist today; `StockLevelReader`'s own docstring
  explicitly scoped bulk read out; meaningfully larger surface, more review risk.
- Effort: Medium–High

### 3. Wire `RegisterStockedProductUseCase` into product creation for initial-stock seeding

Extend `create_admin_product` to accept optional initial quantities per variant and call
the existing (currently dead) use case inside a shared transaction.

- Pros: closes the "products start at 0 until a manual restock" gap; the use case already
  exists and is tested.
- Cons: touches the create-product transaction shape and `ProductForm`, a different flow
  than record/view; conflates two concerns (creation vs. ongoing stock ops) in one change.
- Effort: Medium

## Recommendation

Approach 1, with Approaches 2 and 3 named as explicit deferred follow-ups in the proposal
(not silently dropped). This keeps `admin-stock-management` scoped to what's actually
blocking — an admin path to record movements and see current stock — using only
already-implemented, already-tested domain code, and follows the exact two-prior-changes
pattern (`admin-product-crud`, `admin-product-images`) this repo has already established
twice. Movement history and creation-time stock seeding both require new backend design
work (new ports/use cases) that deserves its own scoped change rather than inflating this
one.

## Risks

- `UnknownVariantError` is not yet handled by `_execute_or_raise` — must be added or a
  `record` call against a stale/foreign `variant_id` will 500 instead of 404.
- No movement-history read port exists — if scope grows to include history (Approach 2),
  this is new port/use-case design work, not just route wiring.
- `StockLevelReader` bulk-read is explicitly out of scope per its own docstring — a
  cross-product stock overview screen (Approach 2) is a materially bigger lift than a
  per-product embedded view (Approach 1).
- RLS policies are correct and already live but have zero anon/service_role integration-test
  coverage in this repo (pre-existing gap, not introduced by or blocking this change).
- `RegisterStockedProductUseCase` is currently dead code — confirm with the user/proposal
  whether "new variants start at 0 stock until a manual restock" is acceptable UX before
  finalizing scope, since it's a real behavioral gap a reviewer may flag.

## Ready for Proposal

Yes. Scope is bounded (Approach 1), all open questions have a recommended default with an
explicit escape hatch to defer, and every reused use case/port signature has been verified
directly against source rather than assumed.
