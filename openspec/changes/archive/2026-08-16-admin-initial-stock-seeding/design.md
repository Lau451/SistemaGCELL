# Design: Admin Initial Stock Seeding

## Technical Approach

`POST /admin/products` stops calling `CreateProductUseCase` and instead calls a
new slug-deriving composition, `CreateStockedProductUseCase`, inside
`transaction(pool)` with `PostgresProductRepository` and
`PostgresStockMovementRepository` built on the SAME connection. That use case
mirrors `CreateProductUseCase` exactly (derive slug → build `Product` →
delegate) but delegates to the already-atomicity-tested
`RegisterStockedProductUseCase`. No domain file changes.

Verified in code: `_to_domain_variants` (admin.py:217) assigns `uuid4()` to
every new variant BEFORE persistence, and `ProductVariant.id: UUID` is a
required construction argument — variant ids are never DB-generated. So seed
movements can be built from the in-memory aggregate with no ordering problem.

## Architecture Decisions

### Decision 1: New `CreateStockedProductUseCase` in `stock/application/`

**Choice**: `backend/src/gcell/stock/application/create_stocked_product.py` —
calls `generate_unique_slug`, builds `Product`, delegates to
`RegisterStockedProductUseCase`.
**Alternatives**: (a) extend `CreateProductUseCase` with a
`StockMovementRepository` — rejected: it lives in `products/application/` and
the documented legal direction is `stock → products`, never the reverse
(`register_stocked_product.py` module docstring); (b) inline slug derivation +
`Product(...)` construction in the route — rejected: admin.py's module
docstring states every write route calls a use case.
**Rationale**: slug logic is reused (`generate_unique_slug` is shared, not
copied); the 4-line wrapper is the same shape the codebase already uses.

### Decision 2: Seed-quantity → movement rule lives in the use case

**Choice**: `execute(..., initial_quantities: Mapping[UUID, int] | None = None)`;
the use case filters `> 0` and builds `StockMovement(RESTOCK, ...)`. The route
supplies a `{variant.id: item.initial_quantity}` dict.
**Alternatives**: build the movement list in an api/ mapper next to
`_to_domain_variants` — rejected: the ">0 or no movement at all" rule is a
business rule the spec places in "the composition", and a keyed mapping avoids
positional-array fragility.
**Rationale**: unit-testable with zero FastAPI; `StockMovement.__post_init__`'s
zero rejection stays a backstop, never the mechanism.

### Decision 3: `_FakePool` in `test_admin.py` must gain `transaction()`

**Choice**: add a `transaction()` async-CM method to the existing `_FakePool`
duck type.
**Rationale**: `transaction()` branches on `isinstance(pool_or_conn,
asyncpg.Pool)`; `_FakePool` is not one, so it hits the else branch and would
raise `AttributeError` → 500. This is a NECESSARY test-fake change, purely
additive (`acquire()`-based routes are untouched). Without it, two currently
green create tests break.

### Decision 4: Field render gated on create mode, not only `row.id === null`

**Choice**: render the input when `row.id === null && productId === undefined`.
**Rationale**: on the edit page a newly added row is also `id === null`, so the
locked `row.id === null` rule alone would show a field PATCH ignores. In create
mode every row is new, so the `variant-initial-quantity` parallel array has
exactly one entry per row; in edit mode it has zero. The positional zip in
`buildVariantsPayload` therefore never misaligns.

## Data Flow

    product-form.tsx (create only) ──variant-initial-quantity──→ actions.ts
      └─ buildVariantsPayload → {..., initial_quantity?: "5"} ──→ POST /admin/products
            └─ AdminVariantInput.initial_quantity (int, ge=0)
                 └─ transaction(pool) ─ conn ─┬─ PostgresProductRepository
                                              └─ PostgresStockMovementRepository
                       └─ CreateStockedProductUseCase → RegisterStockedProductUseCase

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/src/gcell/stock/application/create_stocked_product.py` | Create | Slug-deriving atomic composition (Decisions 1–2) |
| `backend/src/gcell/api/admin.py` | Modify | `initial_quantity` field; `_to_seed_quantities`; route → `transaction(pool)` |
| `backend/tests/unit/stock/test_create_stocked_product_use_case.py` | Create | Mirrors `test_create_product_use_case.py` |
| `backend/tests/integration/api/test_admin_initial_stock.py` | Create | Route-level seed + atomicity |
| `backend/tests/integration/api/test_admin.py` | Modify | `_FakePool.transaction()` (Decision 3) |
| `frontend/.../products/product-form.tsx` | Modify | Create-only "Initial quantity" input |
| `frontend/.../products/actions.ts` | Modify | `initial_quantity` in `VariantWritePayload` |
| `frontend/.../products/product-form.test.tsx`, `actions.test.ts` | Modify | Field/payload coverage |

## Interfaces / Contracts

```python
class AdminVariantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID | None = None
    color: str
    price: Decimal
    cost: Decimal
    initial_quantity: int = Field(default=0, ge=0)  # POST-only; PATCH ignores
```

Purely additive: `extra="forbid"` rejects only UNDECLARED keys, so old payloads
without the field still validate. PATCH now accepts (and ignores) it — the
locked D2 widening.

```ts
interface VariantWritePayload { id?: string; color: string; price: string;
  cost: string; initial_quantity?: string }
```

Relayed verbatim as a string (never `Number()`), matching the existing money
relay convention; blank → key omitted. Pydantic coerces `"5"` → `5`, `"-1"` →
422, `"abc"` → 422.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (py) | slug derivation; `>0` builds one `restock`; `0`/absent builds none | Fake repos, `tests/unit/stock/` |
| Integration (api) | 201 + one `record` call; absent → zero calls; `-1` → 422 with no repo call; PATCH ignores field | `_FakePool` + monkeypatched adapter spies |
| Integration (api+db) | Route-level rollback: 2 seeded variants, `record` raises on the 2nd → zero product/variant rows | Real `db_pool` + `TestClient` (precedent: `test_delete_variant_cross_parent_returns_404_not_403`) |
| Frontend | Field renders in create, absent in edit; payload includes/omits `initial_quantity` | Vitest + Testing Library |

Route-level atomicity IS needed: the existing atomicity test exercises the use
case directly, not the route's new `transaction(pool)` wiring — the one genuinely
new failure mode.

## Threat Matrix

N/A — no shell, subprocess, VCS/PR automation, executable-file classification,
or process-integration boundary. HTTP routing table, auth dependency, and
`_execute_or_raise` mapping are all unchanged.

## Migration / Rollout

No migration required. No schema, trigger, or view change.

## Open Questions

- [ ] None blocking. Decision 4 refines (does not contradict) the proposal's
      `row.id === null` rule for the shared edit form; confirm if the intent was
      to show the field on edit-page new rows too (it would be silently ignored).
