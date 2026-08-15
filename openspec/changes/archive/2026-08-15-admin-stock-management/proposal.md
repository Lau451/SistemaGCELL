# Proposal: Admin Stock Management

## Intent

`backend/src/gcell/stock/` is fully implemented and tested at domain, application, and infrastructure layers, and the append-only ledger, its mutation-rejecting trigger, and the `variant_stock_levels` view are already live — but none of it is reachable from the API. `admin-product-crud` explicitly deferred "stock adjustment UI". The result: the public catalog derives `in_stock` from a ledger the admin has no way to write to, so every restock, sale, breakage, or correction requires raw SQL. This change opens the admin write and read path over the existing use cases, with **zero** changes to the `stock/` domain, application, or infrastructure layers.

## Locked Decisions (scope round — final, not reopened)

1. **Approach 1** from `exploration.md`: record movements + view current per-variant stock, embedded in the existing product edit page. No new ports, no new use cases, no migration.
2. **New variants start at 0 stock** until a manual restock. Confirmed acceptable UX.
3. **No movement history in the UI**: movements are recorded but not listed back in this change.

## Scope

### In Scope

- Two `/admin` routes on the existing `verify_admin_jwt`-gated router, calling only existing use cases.
- `UnknownVariantError` → `404 "not_found"` in `_execute_or_raise` (today unmapped, so a stale or foreign `variant_id` would surface as a `500`).
- Pydantic request/response models with `from_domain`, `ConfigDict(extra="forbid")` on the write body.
- Admin UI: per-variant current stock plus a record-movement form on the product edit page.
- Integration tests mirroring `backend/tests/integration/api/test_admin_images.py`.

### Out of Scope (deferred follow-ups, not dropped)

| Deferred | Rationale |
|---|---|
| Movement history listing | No read port exists for it. `StockMovementRepository` is write-only by design; adding a read there would violate its port shape. Needs new port/use-case design → its own change. |
| Cross-product `/admin/stock` overview | `StockLevelReader`'s own docstring scopes bulk read (`dict[UUID, int]`) out. A cross-product table needs a net-new bulk port. |
| Wiring `RegisterStockedProductUseCase` into product creation | That use case is currently dead code and needs a shared-connection `transaction()` scope; it conflates creation with ongoing stock ops. Deferred per decision 2. |
| Anon/`service_role` RLS integration tests | Pre-existing coverage gap from `supabase-schema` / `public-catalog-screens`; not introduced by, and not blocking, this change. |
| Low-stock thresholds, alerts, reorder points | No domain concept exists today. |

## Capabilities

### New Capabilities

- `admin-stock-management`: admin-facing record-movement and current-stock-view workflows (form, validation feedback, per-variant quantities).

### Modified Capabilities

- `admin-api-access`: adds the stock endpoint contract to the admin router, plus the `UnknownVariantError` → `404` mapping.

`stock-movement-recording` is **not** modified — its use-case and port requirements already describe the exact behavior being exposed, unchanged.

## New Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/admin/products/{product_id}/stock` | Current `quantity_on_hand` per active variant of the product |
| `POST` | `/admin/products/{product_id}/variants/{variant_id}/stock/movements` | Record one movement (`movement_type`, `quantity_delta`, optional `reason`) |

Nesting follows the two established precedents: `/admin/products/{id}/images` (product-scoped collection) and `DELETE /admin/products/{id}/variants/{variant_id}` (variant-scoped action). `.../stock/movements` names the append-only ledger resource, leaving `GET` on the same path free for the deferred history follow-up.

## New Frontend Surfaces

| Surface | Kind | Pattern followed |
|---|---|---|
| `frontend/src/app/api/admin/products/[id]/stock/route.ts` | New GET proxy Route Handler | Exactly `[id]/images/route.ts` |
| `recordStockMovementAction` in `.../admin/products/actions.ts` | New Server Action | Gate → relay → `revalidatePath` → return error; writes never go through a Route Handler (CSRF) |
| `.../admin/products/stock-manager.tsx` | New client component | Mirrors `ImageManager`: props-driven, `router.refresh()` after mutation, no client optimistic state |
| `.../admin/products/[id]/page.tsx` | Modified | Composes `StockManager` alongside `ProductForm` / `ImageManager`, fed `initialStock` from the proxy |

`adminBackendFetch` needs **zero** changes — this is a plain JSON path.

## Approach

Pure wiring. `POST` calls `RecordStockMovementUseCase(repository).execute(variant_id, movement_type, quantity_delta, reason)` — the use case already takes `movement_type` as a plain `str` precisely so an admin route can hand over untyped input, resolving it and raising `ValueError` (→ `422`) before any persistence. `GET` loops `StockLevelReader.quantity_on_hand(variant_id)` over the product's active variants; per-product variant counts are small, so N reads are acceptable and the bulk-read constraint stays untouched. Both routes use `Annotated[asyncpg.Pool, Depends(require_db_pool)]` + `async with pool.acquire() as conn:`, never a bare `Pool`.

**`quantity_delta` is a plain `int`, not a `Decimal`.** The verbatim-string relay discipline this repo mandates for `price`/`cost` does NOT apply here — `Number()` coercion and native number handling are correct for quantity. Stated explicitly so the money-precision rule is not cargo-culted into an unnecessary string relay.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `backend/src/gcell/api/admin.py` | Modified | Two routes, Pydantic models, `UnknownVariantError` mapping |
| `backend/tests/integration/api/test_admin_stock.py` | New | Mirrors `test_admin_images.py` |
| `backend/src/gcell/stock/**` | **Unchanged** | Pure reuse of existing use cases, ports, and adapters |
| `supabase/migrations/` | **Unchanged** | Ledger, trigger, views, and RLS are already live |
| `frontend/src/app/api/admin/products/[id]/stock/route.ts` | New | GET proxy |
| `frontend/src/app/(admin)/admin/products/stock-manager.tsx` | New | Client component |
| `frontend/src/app/(admin)/admin/products/actions.ts` | Modified | `recordStockMovementAction` |
| `frontend/src/app/(admin)/admin/products/[id]/page.tsx` | Modified | Composes `StockManager` |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `UnknownVariantError` unmapped → `500` instead of `404` | High | Explicitly in scope; test with a foreign/stale `variant_id` |
| Admin records a wrong-sign movement (e.g. `sale` positive) | Med | Domain already rejects it; surface the `422` message in the form and constrain sign client-side per type |
| Ledger is append-only — a mistake cannot be edited or deleted | Med | By design: correct with a compensating `adjustment` movement; state this in the UI copy |
| Variant-scoped route lets a valid `variant_id` from another product be used | Med | Verify variant belongs to `product_id`; `404` on mismatch, matching the image ownership check |
| No history means a mis-recorded movement is invisible after submit | Med | Accepted for this slice; the recorded quantity change is visible in the refreshed current-stock read |
| 400-line review budget | Low–Med | Likely 2 slices (backend routes+tests, frontend) — `sdd-tasks`' call |

## Rollback Plan

Revert the change commits. No migration, no new dependency, no new secret, no domain change — nothing to un-apply. `stock_movements` rows written during the trial survive and remain correct: they are exactly the rows the ledger was designed to hold, and the public catalog's `in_stock` derivation already accounts for them. The `/admin` router, product CRUD, and image paths are untouched by a revert.

## Dependencies

- None new. No runtime dependency, no secret, no migration, no Gemini usage.
- Prerequisites already merged: `admin-panel-auth`, `admin-product-crud`, `admin-product-images`, and the `stock/` domain with its live ledger schema.

## Success Criteria

- [ ] Admin records a `restock` from the product edit page; the displayed quantity increases without a manual step.
- [ ] Each of `restock`, `sale`, `return`, `breakage`, `adjustment` records successfully with a correctly-signed delta.
- [ ] A wrong-sign delta and an unknown movement type are both rejected with a clear message and no DB write.
- [ ] A `variant_id` that does not exist, or belongs to another product, returns `404` — never `500`.
- [ ] Current stock reflects the sum of movements (`+10` restock, `-3` sale → `7`).
- [ ] Both stock endpoints return `401` without an admin JWT and never reach the repository.
- [ ] A newly created variant reads `0` and becomes non-zero after one restock.
- [ ] Existing public-catalog, admin-auth, admin-CRUD, and admin-image tests pass unmodified.

## Proposal question round

Decided by the user pre-proposal and **not reopened**: Approach 1 over 2/3; new variants
start at 0 stock; no movement history in this slice; the three deferrals above.

Resolved after the proposal was drafted — **locked, not reopened by `sdd-spec`/`sdd-design`**:

1. **Reason field**: optional for every movement type, matching the use case's
   `reason: str | None = None`. `adjustment`/`breakage` do NOT require a reason.
2. **Client-side sign handling**: the form derives the sign from the selected
   `movement_type` (admin enters a positive magnitude) — a wrong-sign `422` is
   unreachable through the UI, only reachable via a direct API call.
3. **Zero-stock display**: a variant at `0` stock MUST be visually highlighted (distinct
   styling from non-zero rows) in the admin stock view. This is a plain zero/non-zero
   distinction — no configurable low-stock threshold exists in the domain, and none is
   introduced by this change.
