# Exploration: admin-initial-stock-seeding

## Current State

- `POST /admin/products` (`backend/src/gcell/api/admin.py:229-245`) calls `CreateProductUseCase` (`backend/src/gcell/products/application/create_product.py`), which derives a slug then calls `RegisterProductUseCase.execute(product)` → `repository.add(product)`. No stock concept touches this path — `ProductVariant` (`backend/src/gcell/products/domain/product.py`) has **no** stock field; stock is purely derived from the `stock_movements` ledger.
- `PATCH /admin/products/{id}` calls `UpdateProductUseCase` (`backend/src/gcell/products/application/update_product.py`), reconciling `variants` (add-new-id / update-owned-id) in one `repository.update` call. Also no stock concept.
- `AdminVariantInput` (`admin.py:200-206`) is `{id: UUID | None, color, price, cost}` — `id=None` means "new variant". This same Pydantic model is **shared** by both `POST /admin/products` and `PATCH /admin/products/{id}` via `AdminProductWriteRequest.variants`.
- **Key discovery**: `RegisterStockedProductUseCase` (`backend/src/gcell/stock/application/register_stocked_product.py`) already exists, fully built and tested, but is **not wired into any route**. Signature: `execute(product: Product, initial_movements: Sequence[StockMovement] = ())` — calls `products.add(product)` then `movements.record(movement)` for each initial movement. This is exactly the "register product+variants with optional initial stock" operation the change needs.
- Atomicity is already solved and integration-tested: `backend/tests/integration/db/test_register_stocked_product_atomicity.py` proves that when `PostgresProductRepository(conn)` and `PostgresStockMovementRepository(conn)` share the same `asyncpg.Connection` inside `shared.infrastructure.postgres.transaction(pool)`, the whole product+variants+movements insert is one atomic transaction — a failed movement (FK violation → `UnknownVariantError`) rolls back the product and variant rows too, via nested SAVEPOINTs. Composing them under one top-level `transaction(pool)` gives real atomicity with zero new transaction plumbing needed.
- `StockMovement.__post_init__` (`backend/src/gcell/stock/domain/stock_movement.py`) rejects `quantity_delta == 0` unconditionally and requires positive delta for `restock`. Confirmed: "start at 0, no movement" **must skip building a `StockMovement` entirely** — there is no valid zero-quantity movement representation.
- `_execute_or_raise` (`admin.py:97-140`) already maps generic `ValueError` → 422, so a domain-rejected negative/zero `quantity_delta` would surface as 422 automatically if it reached `StockMovement.__post_init__` — though a negative `initial_quantity` is more cleanly rejected at the Pydantic layer (`Field(ge=0)`) before any domain object is built.
- Frontend: `frontend/src/app/(admin)/admin/products/product-form.tsx` renders variant rows (color/price/cost + Remove) shared identically between create (`new/page.tsx`) and edit (`[id]/page.tsx`) — same `rows` state, same field names, distinguishing new-vs-existing rows only by `row.id === null`. `actions.ts`'s `buildVariantsPayload` zips `variant-id`/`variant-color`/`variant-price`/`variant-cost` positionally via `formData.getAll()`. A new `variant-initial-quantity` field would follow this exact parallel-array pattern.

## Affected Areas

- `backend/src/gcell/api/admin.py` — `create_admin_product` must switch its composition root from `CreateProductUseCase`+`pool.acquire()` to a slug-deriving flow that builds `initial_movements` and calls `RegisterStockedProductUseCase` inside a shared-connection `transaction(pool)` scope. `AdminVariantInput` needs a new optional `initial_quantity` field.
- `backend/src/gcell/products/application/create_product.py` — does not currently accept movements; needs extension or a new thin composition wrapper (matching the existing legal `stock -> products` dependency direction already used by `RegisterStockedProductUseCase`/`RecordVariantStockMovementUseCase`).
- `backend/src/gcell/stock/application/register_stocked_product.py` — reusable as-is; needs a slug-deriving caller.
- `backend/src/gcell/products/application/update_product.py` — has no equivalent atomic stock-seed capability; PATCH-time seeding would need new plumbing.
- `frontend/src/app/(admin)/admin/products/product-form.tsx` — new "Initial quantity" input per variant row, naturally scoped to `row.id === null` (new variant only).
- `frontend/src/app/(admin)/admin/products/actions.ts` — `buildVariantsPayload`/`VariantWritePayload` need `initial_quantity` parsed from a new `variant-initial-quantity` field.

## Approaches

1. **Wire `RegisterStockedProductUseCase` into `POST /admin/products`** — a slug-deriving composition builds `initial_movements` from `AdminVariantInput.initial_quantity`, constructing `StockMovement(RESTOCK, quantity_delta=initial_quantity)` only when `initial_quantity > 0`, skipping it entirely otherwise.
   - Pros: Reuses an already-written, already atomicity-tested use case; stays within the existing hexagonal `stock -> products` direction; domain already treats a seed as "just a restock movement" — no special-casing needed.
   - Cons: The route currently does `pool.acquire()` only, not `transaction()` — wiring this in requires changing the route's connection-acquisition pattern (small but real change to existing tested code).
   - Effort: Low-Medium — the hard atomicity part is done.

2. **Create variant, then fire a best-effort follow-up call to the existing `POST .../stock/movements` route/use case after the variant's UUID is known.**
   - Pros: Zero backend route changes possible if orchestrated purely from the frontend as two sequential calls.
   - Cons: Reintroduces exactly the partial-failure risk the task flagged — variant created, seed movement fails, admin sees a "successful" creation with silently-0 stock and no atomic guarantee. Discards the atomicity work already built and tested for no real benefit versus Approach 1.
   - Effort: Low, but strictly worse safety for comparable effort.

## Recommendation

Approach 1. The codebase already contains and integration-tests the exact atomic composition needed (`RegisterStockedProductUseCase`), apparently built ahead of use in a prior change but never wired into a route. The proposal should scope this as "wire an existing atomic use case into `POST /admin/products`," not "build new atomicity machinery." Recommend **POST-only** (brand-new variants only) for v1, deferring PATCH-time seeding since `UpdateProductUseCase` has no equivalent atomic composition and `AdminVariantInput` is shared between POST/PATCH bodies (a complication worth flagging, not resolving here).

## Risks

- `AdminVariantInput` is shared between POST and PATCH bodies — adding `initial_quantity` means it will also arrive on PATCH requests unless explicitly ignored/rejected there or split into a separate model. Needs a proposal-phase decision.
- Negative/zero `initial_quantity` validation point (Pydantic `Field(ge=0)` vs. domain `ValueError`) needs to be decided; domain rejection works and maps to 422 automatically, but Pydantic gives a cleaner error message.
- `create_admin_product` currently does `pool.acquire()` only, not `transaction(pool)` — wiring in the atomic use case is a real (if small) change to the route's connection pattern.
- Whether a partial-failure retry/warning surface is ever needed is moot if Approach 1 is chosen, since partial failure becomes structurally impossible — flagged only for completeness, not resolved here.

## Ready for Proposal

Yes — the central technical risk (atomicity) is already resolved and tested in the existing codebase, significantly de-risking this change. The proposal phase should decide: (1) POST-only vs. also PATCH-time seeding, (2) validation layer for negative/zero `initial_quantity`, (3) whether `AdminVariantInput` needs to split into POST-only vs. shared variants, and (4) exact frontend field wording/UX.

## Explicitly Out of Scope
- Cross-product stock overview (separate planned SDD change, not yet started).
- PATCH-time seeding of stock for existing zero-stock variants (deferred; flag in proposal, do not scope in for v1).
