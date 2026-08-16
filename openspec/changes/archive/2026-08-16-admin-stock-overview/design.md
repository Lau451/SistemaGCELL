# Design: Admin Stock Overview

## Technical Approach

One new read port (`CatalogStockLevelsReader`) implemented as an added method on
the two EXISTING `StockLevelReader` adapters, backed by a single
`WHERE variant_id = ANY($1::uuid[])` query over `variant_stock_levels` (D3).
`list_admin_products` acquires one connection, calls `list_all()` then the bulk
reader once, and serializes through list-only response models (D2 — same route,
same endpoint). Frontend adds a per-variant quantity plus the existing zero-stock
treatment (D5). No migration, no domain change, no new endpoint, no new proxy.

## Architecture Decisions

### Decision 1: New sibling Protocol; method added to the existing adapters

| Option | Tradeoff | Decision |
|---|---|---|
| Add the method to `StockLevelReader` | `tests/unit/stock/test_stock_level_reader_port.py:17` asserts `public_members == {"quantity_on_hand"}`; widening the Protocol **breaks a green test**, contradicting the success criterion "existing stock tests pass unmodified" | Rejected |
| New `CatalogStockLevelsReader` Protocol in its own file, mirroring `StockMovementHistoryReader` | Port isolation is forced by the test above, not merely stylistic | **Chosen** |
| New `PostgresCatalogStockLevelsReader` adapter class | The `StockMovementHistoryReader` precedent split adapters because `PostgresStockMovementRepository`'s docstring says "`record` is its only method" (a WRITE adapter). `PostgresStockLevelReader` is already the read adapter for this exact view and its docstring is not falsified by a plural read | Rejected |

The precedent is followed where its reason holds (Protocol) and not where it does
not (adapter class). Matches the proposal's Affected Areas, which marks both
adapter files "Modified".

### Decision 2: Totality lives in the adapter, not the route

`GROUP BY` emits no row for a variant with zero movements. The adapter seeds
`{vid: 0 for vid in variant_ids}` and overlays fetched rows, so the port contract
is "one entry per requested id" — the route never writes `.get(id, 0)` and the
in-memory adapter is held to the same rule. Empty input short-circuits to `{}`
with zero round trips. Note: the view's column is `quantity_on_hand`, not
`quantity` (`supabase/migrations/20260810000458_public_catalog_rls.sql:21`).

### Decision 3: List-only response models, not a widened `AdminProductResponse`

`AdminProductResponse` is shared by four routes (list, GET by id, POST 201, PATCH
200). A required `quantity_on_hand` on `AdminProductVariantResponse` changes
three other contracts and forces either a fabricated `0` or extra stock reads on
write paths; an `int | None` field violates "not `null`, not a missing key".
→ new `AdminProductListItemResponse` / `AdminProductListVariantResponse`, exactly
the `AdminStockMovementHistoryItemResponse` precedent. `from_domain(product,
quantities)` on the new item model. **Not a D2 deviation**: the wire response of
`GET /admin/products` gains the field as locked; only the internal Pydantic class
differs. A subclass would NOT work — Pydantic serializes by declared field type
and would silently drop the extra key.

### Decision 4: D6 needs no new mechanism

`list_admin_products` does not use `_execute_or_raise` today (no use case, no
mapped application exception). Leave it that way: an `asyncpg` failure in the
bulk read propagates and FastAPI returns 500 with no body — identical to how a
`list_all()` failure already behaves. Wrapping it would be actively wrong:
`_execute_or_raise` maps `ValueError`/`TypeError` to **422**, mislabelling a
driver failure as a client error. The proxy relays the status verbatim, so
`page.tsx`'s existing `!response.ok → null` renders "Unable to load products."

### Decision 5: Zero-stock reuse is literal

`stock-manager.tsx:98-109` distinguishes zero stock with the `text-destructive`
class plus an **"Out of stock"** text label — the semantic proxy its tests
assert. The list reuses both, same label string, same class. No new convention.

## Data Flow

    page.tsx ─fetch─▶ /api/admin/products (unchanged passthrough)
                             │ adminBackendFetch
                             ▼
    list_admin_products ── pool.acquire() ─┬─ PostgresProductRepository.list_all()
                                           └─ quantities_for_variants([all variant ids])
                                                 └─ 1 query: variant_stock_levels
                             ▼
    AdminProductListItemResponse.from_domain(product, quantities)

## File Changes

| File | Action | Description |
|---|---|---|
| `backend/src/gcell/stock/application/catalog_stock_levels_reader.py` | Create | `CatalogStockLevelsReader` Protocol (Decision 1) |
| `backend/src/gcell/stock/infrastructure/postgres_stock_level_reader.py` | Modify | `ANY($1::uuid[])` query + totality overlay |
| `backend/src/gcell/stock/infrastructure/in_memory_stock_level_reader.py` | Modify | Same method, single pass over movements |
| `backend/src/gcell/api/admin.py` | Modify | Two list response models + route composition |
| `backend/tests/unit/stock/test_catalog_stock_levels_reader_port.py` | Create | Port-shape proof |
| `backend/tests/integration/db/test_stock_movement_repository.py` | Modify | Already hosts the level-reader db tests + `make_persisted_variant_id` |
| `backend/tests/integration/api/test_admin.py` | Modify | List route (proposal said `test_admin_products.py`; that file does not exist) |
| `frontend/src/app/(admin)/admin/products/page.tsx` | Modify | `quantity_on_hand` on the local interface + render |
| `frontend/src/app/(admin)/admin/products/page.test.tsx` | Modify | Quantity + zero-stock coverage |
| `supabase/migrations/**`, `stock/domain/**`, `api/admin/products/route.ts` | Unchanged | Verified |

## Interfaces / Contracts

```python
class CatalogStockLevelsReader(Protocol):
    async def quantities_for_variants(
        self, variant_ids: Sequence[UUID]
    ) -> dict[UUID, int]: ...   # one entry per requested id; absent -> 0
```

```sql
SELECT variant_id, quantity_on_hand
FROM variant_stock_levels
WHERE variant_id = ANY($1::uuid[]);  -- index-only scan; one round trip
```

```ts
interface AdminProductVariant { id: string; color: string; price: string;
  cost: string; quantity_on_hand: number }
```

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit (port) | New port declares exactly `{quantities_for_variants}`; `test_stock_level_reader_port.py` stays green **unmodified** | New port-shape test, mirrors the three existing ones |
| Unit (in-memory) | Zero-movement id → `0`; unknown id → `0`; `[]` → `{}`; sums match `quantity_on_hand` | `InMemoryStockLevelReader` + `StockMovement` fixtures |
| Integration (db) | Bulk result equals per-variant `quantity_on_hand`; missing-row variant → `0`; other variants excluded | Extend `test_stock_movement_repository.py` (`db_conn`) |
| Integration (api) | Every variant carries an int; N products/M variants → reader called **exactly once** (D3); bulk read raising → 500, no partial body (D6) | `test_admin.py` + spy adapter, `_FakePool` precedent |
| Frontend | Quantity rendered per variant; `0` shows "Out of stock"; non-zero does not; zero-variant product still renders | Extend `page.test.tsx` |

## Threat Matrix

N/A — no routing table change, no shell, subprocess, VCS/PR automation,
executable-file classification, or process integration. Read-only: no new user
input (no body, no query param, no path param), no schema change, and the auth
dependency, proxy allowlist, and `_execute_or_raise` mapping are all untouched.

## Migration / Rollout

No migration required. No schema, view, index, trigger, dependency, or feature
flag. Single-commit revert restores the prior response shape.

## Open Questions

None. Decision 3's list-only scope was confirmed by the user on 2026-08-16 via
AskUserQuestion and is now locked as proposal.md Decision D7: stock appears only
on `GET /admin/products`; POST/PATCH/GET-by-id are unchanged.
