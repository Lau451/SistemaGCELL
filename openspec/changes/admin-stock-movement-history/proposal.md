# Proposal: Admin Stock Movement History

## Intent

`admin-stock-management` made the ledger writable but not readable: after an admin records a movement, the only feedback is the recomputed total. A mis-typed delta, a duplicate submit, or "who changed this and why" is invisible — the ledger is append-only, so a mistake can only be corrected by a compensating `adjustment`, which an admin cannot do without first *seeing* what was recorded. That change's own design listed "Movement history listing" as a deferred follow-up. This is that follow-up: a read-only, per-variant view of the existing `stock_movements` rows on the product detail page.

## Locked Decisions

1. **Per-variant route only**: `GET /admin/products/{product_id}/variants/{variant_id}/stock/movements` — the path `POST` already owns. No cross-variant or cross-product rollup.
2. **New read port + use case**: `StockMovementHistoryReader` (new Protocol, leaves the write-only `StockMovementRepository` untouched) plus `ListVariantStockMovementsUseCase`, mirroring `RecordVariantStockMovementUseCase`'s product-fetch → variant-ownership-guard → delegate shape. The guard makes this more than the "for loop" that justified `GET .../stock`'s route-level composition.
3. **Keyset pagination on `id DESC`**: `id` is a monotonic identity column on an append-only table, so PK order *is* chronological order. **No migration, no new index.** `created_at`-ordered paging would require one; explicitly rejected.
4. **Pagination contract**: `?limit` (default 20, max 100) + `?before_id` (exclusive cursor). Response `{ items, next_before_id }`, `next_before_id = null` at the end. This is the backend's first pagination pattern and the intended precedent for the two planned follow-ups.
5. **Foreign/unknown `variant_id` → `404`, never `403`**, via `VariantNotFoundError` and the existing `_execute_or_raise` mapping. A variant with zero movements is `200` with an empty list.

## Scope

### In Scope

- New read port, Postgres adapter query, list use case, GET route + Pydantic models.
- Frontend: new proxy route handler, `fetchAdminProductStockHistory`, history UI on the product detail page (`stock-manager.tsx` or a sibling), following the `initialX` prop + `router.refresh()` convention.
- Integration tests extending `test_admin_stock.py` and `test_stock_movement_repository.py`.

### Out of Scope

| Deferred | Rationale |
|---|---|
| Cross-product stock overview | Planned follow-up #2; needs a bulk port. |
| Initial-stock seeding | Planned follow-up #3. |
| Filter by movement type / date range | Keeps this slice a plain listing; adds query-shape and index questions. |
| Edit/delete of movements | Structurally impossible — the trigger rejects mutation. |
| Actor attribution ("who") | No `recorded_by` column exists; needs schema work. |

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `stock-movement-recording`: adds a read-side listing port and use case (read-only; the no-update/no-delete invariant is unchanged).
- `admin-stock-management`: adds the admin history view behavior.
- `admin-api-access`: adds the history endpoint contract and its pagination parameters.

## Approach

`ListVariantStockMovementsUseCase(products, history)` loads the product, raises `VariantNotFoundError` unless `variant_id` is in `product.variants`, then delegates to `StockMovementHistoryReader.list_for_variant(variant_id, limit, before_id)`. The adapter runs `SELECT ... FROM stock_movements WHERE variant_id = $1 AND ($2::bigint IS NULL OR id < $2) ORDER BY id DESC LIMIT $3`, served by the existing `variant_id` index. The route returns domain objects mapped through a `from_domain` response model, consistent with every other admin route.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `backend/src/gcell/stock/application/stock_movement_history_reader.py` | New | Read-only Protocol |
| `backend/src/gcell/stock/application/list_variant_stock_movements.py` | New | Use case with ownership guard |
| `backend/src/gcell/stock/infrastructure/postgres_stock_movement_repository.py` | Modified | Keyset `SELECT` (new adapter class or added method) |
| `backend/src/gcell/api/admin.py` | Modified | GET route + response models |
| `backend/src/gcell/stock/domain/**`, `supabase/migrations/` | **Unchanged** | No domain change, no migration, no index |
| `frontend/src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/route.ts` | New | GET proxy, mirrors `stock/route.ts` |
| `frontend/src/app/(admin)/admin/products/[id]/page.tsx` | Modified | History fetch + prop wiring |
| `frontend/src/app/(admin)/admin/products/stock-manager.tsx` | Modified/New sibling | History table |
| `backend/tests/integration/api/test_admin_stock.py`, `.../db/test_stock_movement_repository.py` | Modified | Route + adapter coverage |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Pagination shape copied by the next two follow-ups | High | Deliberately locked as keyset; documented as the precedent |
| `id DESC` diverges from `created_at` order | Very Low | Identity column on an append-only, mutation-rejecting table |
| Sequential scan as the ledger grows | Low | Existing `variant_id` index filters; per-variant row counts are small. Revisit with a `(variant_id, id DESC)` index if measured |
| Full-history reading via `limit` abuse | Low | Hard cap of 100 enforced server-side |
| 1200-line review budget | Low | Backend + frontend; `sdd-tasks`' slicing call |

## Rollback Plan

Revert the change commits. No migration, no dependency, no secret, no domain change, no write path touched — nothing to un-apply. The ledger, the record-movement route, and the current-stock read are all untouched by a revert.

## Dependencies

- None new. Prerequisite `admin-stock-management` is merged and archived.

## Success Criteria

- [ ] An admin sees a variant's movements newest-first with date, type, delta, and reason on the product detail page.
- [ ] A variant with no movements renders an empty state, and the endpoint returns `200` with an empty list.
- [ ] `limit` above the cap is clamped, not honored; a bad cursor is rejected without a `500`.
- [ ] Paging with `before_id` returns strictly older rows with no duplicates or gaps.
- [ ] A `variant_id` from another product returns `404` — never `403`, never another product's rows.
- [ ] The endpoint returns `401` without an admin JWT and never reaches the database.
- [ ] `supabase/migrations/` is unchanged and existing stock tests pass unmodified.

## Proposal question round

Automatic pace — items 1–3 were user-facing calls with a recommended default written into this
proposal. **Confirmed by the user on 2026-08-15 via AskUserQuestion: all three recommended
defaults accepted as-is, no changes.** Item 4 was recorded as decided (not asked).

1. **Resulting balance after each movement** — **confirmed: defer.** Including it needs
   `SUM(quantity_delta) OVER (PARTITION BY variant_id ORDER BY id)`, which scans the variant's
   whole partition per page and is only correct on a full-history read. The current total is
   already displayed above the history.
2. **Pagination UX** — **confirmed: last 20 newest-first with a "Load more" button** appending
   pages, cursor held in component state only (a `router.refresh()` after recording a movement
   resets to page 1, which is correct).
3. **Per-variant-only presentation** — **confirmed:** a product with several variants means the
   admin views history one variant at a time (expand/select per variant), matching the existing
   POST route's scoping and avoiding overlap with the out-of-scope cross-product overview.
4. **Type/date filters** — decided: **out of scope**, per the table above.

These four are now locked and must not be reopened by `sdd-spec` or `sdd-design`.
