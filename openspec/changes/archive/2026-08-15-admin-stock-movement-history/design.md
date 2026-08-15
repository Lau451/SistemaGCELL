# Design: Admin Stock Movement History

## Technical Approach

Read-side slice over the existing `stock_movements` ledger. New port + use case + Postgres adapter (proposal Locked Decision 2), keyset-paged on `id DESC` (LD 3), exposed at `GET /admin/products/{product_id}/variants/{variant_id}/stock/movements` (LD 1) with `?limit`/`?before_id` → `{items, next_before_id}` (LD 4). Frontend adds a proxy Route Handler, a server prefetch, and a new client component. No migration, no domain change.

## Architecture Decisions

### Decision 1: Application-layer read model, not an extended `StockMovement`

| Option | Tradeoff | Decision |
|---|---|---|
| Add `id`/`created_at` to `StockMovement` | Breaks the frozen value-object's documented equality rationale ("id is DB-assigned … value equality is correct here"); forces `None` at every write site; violates "domain unchanged" | Rejected |
| New frozen `RecordedStockMovement` in `application/` | Domain stays byte-identical; no `__post_init__` re-validation on read; write model vs. read model split already implicit in `StockLevelReader` | **Chosen** |

**Deviation flag**: the proposal says the route "returns domain objects". It cannot — `StockMovement` carries neither `id` (the cursor) nor `created_at` (the required date column). This resolves that gap without reopening any locked decision. Reuses the domain `MovementType` enum. Colocated in the port file (its only consumer).

### Decision 2: New sibling adapter class, not a method on `PostgresStockMovementRepository`

Read and write adapters are **already split for the same ledger data**: `PostgresStockLevelReader` reads the derived view, `PostgresStockMovementRepository` only INSERTs and its docstring states "`record` is its only method, mirroring the `StockMovementRepository` port shape". Adding `list_for_variant` there would falsify that docstring and its per-write `transaction()` rationale. → new `PostgresStockMovementHistoryReader` (+ `InMemoryStockMovementHistoryReader`, per the one-in-memory-adapter-per-port convention).

### Decision 3: Clamp in the use case; fetch `limit + 1`

`limit` is clamped (`max(1, min(limit, 100))`, default 20) in the use case, **not** via `Query(le=100)` — FastAPI validation would 422 instead of clamping (LD 4 says clamp). Non-integer `limit`/`before_id` still 422 via type coercion, never 500. The use case requests `limit + 1` rows and trims, so `next_before_id` is `null` exactly at the end rather than after one wasted round-trip. Returns a frozen `StockMovementPage(items, next_before_id)` — the named precedent for the two planned follow-ups.

### Decision 4: Response models carry no `ConfigDict`

Verified in `admin.py`: `extra="forbid"` appears only on **request** models; every response model has no `model_config`. New `AdminStockMovementHistoryItemResponse` is separate from `AdminStockMovementResponse` (adding `id`/`created_at` there would change the POST 201 contract).

### Decision 5: New `stock-history.tsx`, not an extension of `stock-manager.tsx`

`stock-manager.tsx` is already 216 lines with two responsibilities, is scoped **per product**, and has no client data lifecycle. History is **per variant**, client-paginated, and client-fetched. Separate sibling component + `stock-history.test.tsx`, rendered by `[id]/page.tsx` below `StockManager`.

### Decision 6: `StockHistory` owns local `useState` — deliberate deviation

`stock-manager.tsx` states "`stock` intentionally has NO local `useState`". An append-in-place "Load more" list cannot be expressed by a server prop, which only ever describes page 1. Server-driven `?before_id` URL paging was considered and rejected: it *replaces* rather than appends, would need every prior cursor in the URL (O(n²) refetch), and would remount the sibling product/image forms on each click. **Already user-confirmed** — proposal Q2 locks "cursor held in component state only". Reset on `router.refresh()` uses React's compare-prop-during-render pattern (no effect): when the `initialHistory` reference changes, entries and cursor reset to page 1.

### Decision 7: Allowlisted query passthrough in the proxy

The Route Handler forwards **only** `limit` and `before_id`, rebuilt into a fresh `URLSearchParams` — never `new URL(request.url).search` verbatim, which would let a client inject arbitrary params into the backend URL.

## Data Flow

    page.tsx ──fetchAdminProductStockHistory(id, variants[0].id)──┐
                                                                  ▼
    StockHistory (client) ──"Load more"/variant switch──▶ /api/.../movements/route.ts
                                                                  │ adminBackendFetch
                                                                  ▼
    admin.py GET ─▶ ListVariantStockMovementsUseCase ─▶ products.get_by_id
                          │  (VariantNotFoundError → 404, never 403)
                          └─▶ StockMovementHistoryReader.list_for_variant ─▶ stock_movements

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/src/gcell/stock/application/stock_movement_history_reader.py` | Create | `StockMovementHistoryReader` Protocol + `RecordedStockMovement` read model |
| `backend/src/gcell/stock/application/list_variant_stock_movements.py` | Create | Use case + `StockMovementPage`; ownership guard, clamp, `limit+1` trim |
| `backend/src/gcell/stock/infrastructure/postgres_stock_movement_history_reader.py` | Create | Keyset `SELECT` |
| `backend/src/gcell/stock/infrastructure/in_memory_stock_movement_history_reader.py` | Create | Test adapter |
| `backend/src/gcell/api/admin.py` | Modify | GET route + two response models |
| `backend/src/gcell/stock/domain/**`, `supabase/migrations/**` | Unchanged | Verified: no new file under `domain/`, `test_domain_boundary.py` unaffected |
| `frontend/src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/route.ts` | Create | GET proxy |
| `frontend/src/app/(admin)/admin/products/stock-history.tsx` | Create | History table + "Load more" |
| `frontend/src/app/(admin)/admin/products/[id]/page.tsx` | Modify | `fetchAdminProductStockHistory` + prop wiring |

## Interfaces / Contracts

```python
class StockMovementHistoryReader(Protocol):
    async def list_for_variant(
        self, variant_id: UUID, limit: int, before_id: int | None
    ) -> list[RecordedStockMovement]: ...
```

```sql
SELECT id, variant_id, movement_type, quantity_delta, reason, created_at
FROM stock_movements
WHERE variant_id = $1 AND ($2::bigint IS NULL OR id < $2)
ORDER BY id DESC LIMIT $3;   -- served by stock_movements_variant_id_covering_idx
```

```ts
async function fetchAdminProductStockHistory(
  id: string, variantId: string,
): Promise<AdminStockMovementPage>;  // { items: AdminStockMovement[]; next_before_id: number | null }
```

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit (port) | `StockMovementHistoryReader` declares exactly `{list_for_variant}` | New `test_stock_movement_history_reader_port.py`, mirrors the two existing port-shape proofs |
| Unit (use case) | Foreign variant → `VariantNotFoundError` **with zero reader calls**; unknown product → `ProductNotFoundError`; clamp `0→1`, `500→100`, default 20; `limit+1` trim; `next_before_id is None` at end; empty variant → `[]` | New `test_list_variant_stock_movements.py` + in-memory adapters |
| Integration (db) | `id DESC` order, `before_id` exclusivity, no duplicates/gaps across pages, variant isolation | **Extend** `test_stock_movement_repository.py` — same table, reuses its `db_conn` seed helpers |
| Integration (api) | 401 without JWT and no DB touch; 404 `"not_found"` for a foreign variant; `?limit=500` clamped; `?before_id=abc` → 422 not 500; `{items, next_before_id}` shape | Extend `test_admin_stock.py` (TestClient + forged JWT + spy adapters) |
| Frontend | Proxy: 401 / 502 / only `limit`+`before_id` forwarded. Component: empty state, newest-first, "Load more" appends, button hidden when `next_before_id` is null, reset on new `initialHistory` | New `movements/__tests__/route.test.ts` + `stock-history.test.tsx`; extend `[id]/page.test.tsx` |

## Threat Matrix

| Boundary | Applicability |
|---|---|
| Documentation-like paths | N/A — no file classification or execution |
| Git repository selection | N/A — no VCS automation |
| Commit state | N/A |
| Push state | N/A |
| PR commands | N/A |

No shell, subprocess, VCS, or process-integration boundary — the matrix rows do not apply. The one adjacent surface (HTTP query passthrough in the Next.js proxy) is handled by Decision 7 and covered by the proxy route test.

## Migration / Rollout

No migration required. No new index, no schema change, no new dependency, no feature flag. Revert restores prior behavior exactly — the write path and current-stock read are untouched.

## Open Questions

- [ ] `stock_movements.id` is `bigint`; JSON numbers lose precision above 2^53. Accepted for now (row counts are far below that); revisit as a string-encoded cursor if the ledger ever approaches it.
- [ ] Multi-variant products prefetch only `variants[0]`'s history server-side; switching variants is a client fetch through the same proxy. Consistent with proposal Q3's "one variant at a time".
