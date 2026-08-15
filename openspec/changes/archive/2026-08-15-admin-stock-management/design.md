# Design: Admin Stock Management

## Technical Approach

Pure wiring over the already-complete `stock/` domain, with **one exception**: the variant-scoped
write needs an IDOR guard, and this repo's `admin-product-images` spec requires ownership be
"Checked At The Use-Case Layer", while `admin.py`'s module docstring forbids a write route from
calling `PostgresProductRepository` directly. `RecordStockMovementUseCase` has no concept of
`product_id`, so the guard gets one new thin composition use case —
`RecordVariantStockMovementUseCase` in `stock/application/` (the `stock -> products` direction is
already legal and exercised by `RegisterStockedProductUseCase`). It adds **no new port, no new
domain concept, no migration**, and leaves every existing `stock/` module byte-identical. The GET
route is a read and follows `list_admin_product_images`' precedent: it calls the repository/reader
directly, no use case. Frontend mirrors `ImageManager` file-for-file.

## Architecture Decisions

| # | Decision | Rejected alternative | Rationale |
|---|---|---|---|
| 1 | Ownership guard in a new `RecordVariantStockMovementUseCase(products, record_movement)` that resolves the product, scans `product.variants` for `variant_id`, then delegates | (a) Route resolves the product via `PostgresProductRepository` before calling the use case; (b) add `product_id` to `RecordStockMovementUseCase`; (c) rely on the FK's `UnknownVariantError` alone | (a) violates `admin.py`'s stated rule that write routes call use cases only, never repository methods — the rule exists precisely because guards belong in use cases. (b) changes a tested use case's constructor and contradicts the proposal's `stock/**` **Unchanged** row far more invasively than one additive module. (c) is not a guard at all: the FK proves the variant exists, not that it belongs to `product_id` — IDOR passes. The scan runs against the already-fetched aggregate, never a SQL join, exactly like `UploadProductImageUseCase`. |
| 2 | GET loops `StockLevelReader.quantity_on_hand` **inside the route handler** | A `ListProductStockUseCase` in `stock/application/` | `list_admin_product_images` and `get_admin_product` both establish that a read route composes repositories/readers directly. A use case here would own no decision — only a `for` loop — and would need the `products` port too, duplicating decision 1's shape for zero authorization value. Bulk-read stays out of scope per `StockLevelReader`'s docstring; per-product variant counts are small. |
| 3 | `UnknownVariantError` joins the existing `except (ProductNotFoundError, VariantNotFoundError, ImageNotFoundError)` tuple → `404 "not_found"` | A dedicated `except` block with its own detail string | Same IDOR-safe generic body as the other three; a distinct detail would leak "this variant exists elsewhere". **Consequence of decision 1**: this becomes defense-in-depth — the ownership scan already 404s before `record` is reached, so a route-level scenario cannot reach it (variants are only ever soft-deleted, never hard-deleted). It stays in scope as a guarantee, tested at the mapper. |
| 4 | `movement_type` typed `str` in the request model | Pydantic `Literal["restock", ...]` or the `MovementType` enum | `MovementType` is the single source of truth; a `Literal` duplicates it and drifts. Both yield 422 — via `RecordStockMovementUseCase`'s `ValueError` — but the domain path produces a message naming the rejected value. Matches the use case's documented "callers hand over untyped input" contract. |
| 5 | `quantity_delta` is a plain `int` end to end; `Number()` coercion in the Server Action is correct | Verbatim-string relay | The string relay exists only for `price`/`cost` (`Decimal`). Stated so the money rule is not cargo-culted onto quantity (proposal, Approach). |
| 6 | One record-movement form with a variant `<select>`, `recordStockMovementAction.bind(null, productId)` under a single `useActionState` | One `useActionState` per variant row | Hooks cannot be called in a loop; per-row forms would need a child component each. One form + a list above it is exactly `ImageManager`'s shape (its upload form also carries the variant select). The action reads `variant-id` from `FormData` to build the variant-scoped path. |
| 7 | Sign derived in an exported pure `signedQuantityDelta(movementType, magnitude, direction)`; admin enters a positive magnitude; `direction` is honoured **only** for `adjustment` | Free-signed number input; conditionally rendering `direction` only when `adjustment` is selected | Locked decision 2 makes a wrong-sign 422 unreachable through the UI. A pure function is unit-testable without rendering; always rendering `direction` avoids client state that `ImageManager` does not have. The domain check stays authoritative and its 422 is still surfaced. |
| 8 | Zero stock highlighted by a conditional Tailwind class + an "Out of stock" label | A configurable low-stock threshold | Plain zero/non-zero only (locked decision 3) — no threshold concept exists in the domain. Uses tokens already in `image-manager.tsx` (`text-destructive`, `text-muted-foreground`, `border-border`). |

## Data Flow

```
READ
[id]/page.tsx (RSC) --cookie--> /api/admin/products/{id}/stock --> GET /admin/products/{id}/stock
        |                          (adminBackendFetch)            | 401 router / 503 db
        v                                                          v
   StockManager <--initialStock--                 PostgresProductRepository.get_by_id -> 404
                                                  per active variant: quantity_on_hand(v.id)

WRITE
form --FormData--> recordStockMovementAction(productId) --JSON--> POST /admin/products/{pid}
 (origin-checked)   signedQuantityDelta()  adminBackendFetch         /variants/{vid}/stock/movements
                                                                     |
                                                     RecordVariantStockMovementUseCase
   1 products.get_by_id            -> ProductNotFoundError  404
   2 variant in product.variants   -> VariantNotFoundError  404   (IDOR guard, no storage/DB write yet)
   3 MovementType(str)             -> ValueError            422
   4 StockMovement(...) sign/zero  -> ValueError            422   (still no write)
   5 repository.record -> INSERT   -> UnknownVariantError   404   (defensive, see Decision 3)
        -> 201 -> revalidatePath(detail) -> router.refresh() -> READ re-runs
```

## Interfaces / Contracts

```python
# stock/application/record_variant_stock_movement.py  (the ONLY new backend module)
@dataclass
class RecordVariantStockMovementUseCase:
    products: ProductRepository                      # existing port, reused
    record_movement: RecordStockMovementUseCase      # existing use case, unchanged

    async def execute(
        self, product_id: UUID, variant_id: UUID,
        movement_type: str, quantity_delta: int, reason: str | None = None,
    ) -> StockMovement:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        if not any(v.id == variant_id for v in product.variants):
            raise VariantNotFoundError(variant_id, product_id)   # never 403 (IDOR)
        return await self.record_movement.execute(
            variant_id=variant_id, movement_type=movement_type,
            quantity_delta=quantity_delta, reason=reason,
        )
```

`get_by_id`'s `LEFT JOIN ... AND v.deleted_at IS NULL` means a **soft-deleted** variant is absent
from `product.variants` and therefore 404s — the read-time soft-delete cascade is inherited for
free, no extra query.

```python
# api/admin.py  (new models)
class AdminVariantStockResponse(BaseModel):
    variant_id: UUID
    color: str                  # display context; the UI never re-fetches variants for this
    quantity_on_hand: int

    @classmethod
    def from_domain(cls, variant: ProductVariant, quantity_on_hand: int) -> "AdminVariantStockResponse": ...

class AdminRecordStockMovementRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    movement_type: str          # Decision 4
    quantity_delta: int
    reason: str | None = None   # optional for EVERY type (proposal Q1)

class AdminStockMovementResponse(BaseModel):
    variant_id: UUID
    movement_type: str
    quantity_delta: int
    reason: str | None

    @classmethod
    def from_domain(cls, movement: StockMovement) -> "AdminStockMovementResponse": ...
```

`StockMovement` carries **no id and no timestamp** (`bigint generated always as identity`,
DB-assigned), so the 201 body echoes the recorded values only — it cannot return a movement id.

### Endpoints (existing `verify_admin_jwt`-gated `/admin` router)

| Method | Path | Body | Success |
|---|---|---|---|
| GET | `/admin/products/{product_id}/stock` | — | 200 `list[AdminVariantStockResponse]` |
| POST | `/admin/products/{product_id}/variants/{variant_id}/stock/movements` | JSON, `extra="forbid"` | 201 `AdminStockMovementResponse` |

Both use `Annotated[asyncpg.Pool, Depends(require_db_pool)]` + `async with pool.acquire() as conn:`.
No `require_storage` — this change touches no Storage. Dependency order stays 401 → 503.

```ts
// stock-manager.tsx
export interface AdminVariantStock { variant_id: string; color: string; quantity_on_hand: number }
export interface StockManagerProps { productId: string; initialStock: AdminVariantStock[] }
// no `variants` prop: initialStock already carries color per variant (simpler than ImageManagerProps)

// actions.ts
export type MovementDirection = "increase" | "decrease";
export function signedQuantityDelta(
  movementType: string, magnitude: number, direction: MovementDirection): number;
export async function recordStockMovementAction(
  productId: string, _prevState: ProductFormState, formData: FormData): Promise<ProductFormState>;
```

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/src/gcell/stock/application/record_variant_stock_movement.py` | Create | Ownership guard + delegation (Decision 1) |
| `backend/src/gcell/api/admin.py` | Modify | 2 routes, 3 models, `UnknownVariantError` in the 404 tuple |
| `backend/tests/unit/stock/test_record_variant_stock_movement.py` | Create | Guard tests with a recording spy |
| `backend/tests/integration/api/test_admin_stock.py` | Create | Mirrors `test_admin_images.py` |
| `backend/src/gcell/stock/{domain,infrastructure}/**`, `application/{repository,stock_level_reader,record_stock_movement}.py` | **Unchanged** | Pure reuse |
| `supabase/migrations/` | **Unchanged** | Ledger, trigger, views, RLS already live |
| `frontend/src/app/api/admin/products/[id]/stock/route.ts` | Create | GET proxy, copy of `images/route.ts` |
| `frontend/src/app/(admin)/admin/products/stock-manager.tsx` | Create | Table + single record form |
| `frontend/src/app/(admin)/admin/products/actions.ts` | Modify | `recordStockMovementAction`, `signedQuantityDelta` |
| `frontend/src/app/(admin)/admin/products/[id]/page.tsx` | Modify | `fetchAdminProductStock` + `<StockManager>` |

## Testing Strategy (Strict TDD)

| Layer | Highest-value RED tests |
|---|---|
| Unit — use case | Unknown/retired product → `ProductNotFoundError`, spy proves **zero** `record` calls; valid `variant_id` owned by **another** product → `VariantNotFoundError`, zero `record` calls; soft-deleted variant (absent from `product.variants`) → `VariantNotFoundError`; happy path delegates `variant_id`/`movement_type`/`quantity_delta`/`reason` verbatim and returns the `StockMovement` |
| Unit — mapper | `_execute_or_raise` over an operation raising `UnknownVariantError` → `HTTPException(404, "not_found")` (Decision 3: not reachable end-to-end, so tested here) |
| Integration — api | Both routes 401 with a repository spy proving zero calls; GET 404 unknown product; GET returns `0` for a variant with no movements; POST 404 foreign `variant_id`; 422 for `sale` with `+5`, unknown `movement_type`, `quantity_delta: 0`, blank `reason`, and an extra body field; **201 then GET read-back**: `+10` restock, `-3` sale → `7` |
| Unit — frontend | `signedQuantityDelta` per type (restock/return → `+`, sale/breakage → `-`, adjustment honours `direction`); action builds the variant-scoped path and JSON body, omits blank `reason`, relays quantity as a **number**; 201 → `revalidatePath(detail)` + `{error: null}`; non-201 → `extractAdminError`; `unauthenticated` → redirect to login; a `0` row renders the highlight class and a non-zero row does not |

Existing public-catalog, admin-auth, admin-CRUD, admin-image and all `stock/` suites must pass **unmodified**.

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED tests |
|---|---|---|---|
| IDOR — variant-scoped write with a foreign `variant_id` | **Applicable** — the only new trust boundary | Use-case-layer ownership scan on the fetched aggregate (Decision 1); `404 "not_found"`, never 403, never a distinguishable body; the FK 404 is a second, defensive layer | Foreign-variant unit test asserting zero `record` calls; API 404 test |
| Routing | **Applicable** — 2 new routes | Both inherit router-level `Depends(verify_admin_jwt)`; no per-route auth is introduced | 401 tests with a spy proving zero repository calls |
| Documentation-like paths / executable-file classification | N/A — no file upload, no path derived from user input | — | — |
| Shell / subprocess / process integration | N/A — in-process DB read/write only, no external service call | — | — |
| Git repository selection / commit / push / PR commands | N/A — no VCS automation | — | — |

Materially smaller surface than `admin-product-images`: no Storage, no Pillow, no new secret.

## Migration / Rollout

**No migration.** `stock_movements`, its append-only `BEFORE UPDATE OR DELETE` trigger, the
`variant_stock_levels` view and the RLS grants all shipped in
`20260810000453_stock_movements_ledger.sql` / `20260810000458_public_catalog_rls.sql`. No new env
var, no new runtime dependency, no feature flag — the endpoints are live the moment they deploy.
Rollback = revert the commits; rows written meanwhile are exactly the rows the ledger was designed
to hold and the public `in_stock` derivation already accounts for them.

## Out of Scope

Movement history listing, a cross-product `/admin/stock` overview, wiring
`RegisterStockedProductUseCase` into product creation, and anon/`service_role` RLS integration
tests are **explicitly deferred** — see the proposal's "Out of Scope (deferred follow-ups)" table
for each rationale. None is picked up here even where the code is nearby.

## Open Questions

- [x] Decision 1 adds **one new use-case module**, which reads against locked decision 1's
      "no new use cases". Every alternative either breaks `admin.py`'s write-route rule or leaves
      the IDOR risk the proposal's own Risk table demands be closed. **Acknowledged and accepted by
      the user 2026-08-14**: no new port, no new domain concept, no migration, `stock/**` otherwise
      unchanged.
- [ ] The `UnknownVariantError` → 404 mapping is unreachable end-to-end once the ownership guard
      exists (Decision 3). The spec should phrase it as a **mapping** requirement, not a reachable
      user scenario, or `sdd-verify` will look for an API-level scenario that cannot be written.
- [ ] `StockMovement` has no id/timestamp, so the 201 body cannot echo a movement id — the spec
      must not assert one.
- [ ] `quantity_delta` has no upper bound (Pydantic `int` is unbounded; the domain rejects only
      zero). No bound is introduced because no domain concept exists for one; naming it so a
      reviewer's "why no max?" is answered rather than discovered.
