# Proposal: Admin Initial Stock Seeding

## Intent

Every new variant starts at 0 stock and needs a separate manual restock
movement afterward. Admins onboarding real inventory do the job twice and can
forget the second step, leaving a live product with phantom-zero stock. Let an
admin set an initial quantity per variant while CREATING the product, persisted
atomically with the product itself.

## Scope

### In Scope
- Optional `initial_quantity` (default 0) per variant on `POST /admin/products`.
- Wire the existing, atomicity-tested `RegisterStockedProductUseCase` into that
  route, preserving server-side slug derivation.
- Seed movements recorded as `restock`; quantity 0 records NO movement at all.
- "Initial quantity" input rendered only on new-variant rows (`row.id === null`).

### Out of Scope
- Seeding stock via `PATCH /admin/products/{id}` (variants added on edit keep
  using the existing stock manager).
- Cross-product stock overview (separate, not-started change).
- Any `stock_movements` schema, trigger, or `variant_stock_levels` change — no
  Supabase migration. No Gemini API usage.

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `admin-product-management`: creation accepts an optional per-new-variant
  initial quantity, persisted atomically with product and variants.
- `stock-movement-recording`: specify the already-implemented atomic
  "register product with initial movements" use case and the
  zero-quantity-means-no-movement rule.

## Approach

Exploration Approach 1. `RegisterStockedProductUseCase` is already built and
proven atomic by `backend/tests/integration/db/test_register_stocked_product_atomicity.py`
(shared `asyncpg.Connection` under `transaction(pool)`, nested SAVEPOINTs). This
change WIRES an existing tested use case into a route — it does not build new
atomicity machinery. `create_admin_product` moves from `pool.acquire()` to
`transaction(pool)`, constructs both Postgres repositories on that connection,
derives the slug, builds one `restock` movement per variant with
`initial_quantity > 0`, and calls the use case once.

### Locked Decisions
| # | Decision |
|---|----------|
| D3 | Negative values rejected by Pydantic `Field(ge=0)` (clean 422 before any domain object exists). |
| D4 | Seed movement type is always `restock`. |
| D5 | Frontend field defaults to empty/0; blank means "no stock recorded yet". |

### Proposal Question Round — Confirmed by the user on 2026-08-15 via AskUserQuestion
| # | Question | Decision |
|---|----------|---------------------|
| D1 | POST-only, or also seed on PATCH for existing zero-stock variants? | **Confirmed: POST-only for v1.** `UpdateProductUseCase` has no atomic stock composition; adding it is materially more work. |
| D2 | Keep ONE shared `AdminVariantInput` with `initial_quantity` (ignored on PATCH), or split into POST-only and shared models? | **Confirmed: keep one shared model**; only the POST handler reads the field. Matches the existing "`id: None` means different things per context" pattern. |

Both recommended defaults were accepted as-is, no changes. These are now locked
and must not be reopened by `sdd-spec` or `sdd-design`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/src/gcell/api/admin.py` | Modified | `AdminVariantInput.initial_quantity`; `create_admin_product` switches to `transaction(pool)` + `RegisterStockedProductUseCase`. |
| `backend/src/gcell/stock/application/register_stocked_product.py` | Reused | Consumed as-is; may gain a slug-deriving wrapper. |
| `backend/src/gcell/products/application/create_product.py` | Modified/Bypassed | Superseded on the create path by the stock-side composition. |
| `frontend/.../admin/products/product-form.tsx` | Modified | New-variant-only "Initial quantity" input. |
| `frontend/.../admin/products/actions.ts` | Modified | `variant-initial-quantity` parsed into `VariantWritePayload`. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Shared `AdminVariantInput` leaks the field into PATCH bodies | High | D2 confirmed accepted; PATCH handler never reads it; spec a scenario asserting PATCH ignores it. |
| Rewiring the create route breaks existing product creation | Medium | Existing create tests must stay green unchanged; the zero-quantity path must be byte-equivalent in behavior to today. |
| A zero-delta `StockMovement` is constructed by accident | Medium | Hard domain invariant: `__post_init__` rejects delta 0. Build movements only when `initial_quantity > 0`; cover with a test. |
| Edit-page variant rows show the field and confuse admins | Low | Render only when `row.id === null`. |

## Rollback Plan

Single-commit revert. No migration, no schema change, no data backfill — any
seed movements already written stay valid `restock` rows in the append-only
ledger and remain correct after revert. The route reverts to
`pool.acquire()` + `CreateProductUseCase` with no residual state.

## Dependencies

- `admin-stock-management` (archived) and `admin-stock-movement-history`
  (archived) — both shipped; no blocking dependency remains.

## Success Criteria

- [ ] Creating a product with `initial_quantity: 5` yields current stock 5 with
      exactly one `restock` movement, no second request needed.
- [ ] Creating a product with `initial_quantity` absent/0 records zero movements.
- [ ] A failure while recording a seed movement rolls back the product and all
      variant rows (nothing partially persisted).
- [ ] Negative `initial_quantity` returns 422 before any write is attempted.
- [ ] `PATCH /admin/products/{id}` behavior is unchanged.
