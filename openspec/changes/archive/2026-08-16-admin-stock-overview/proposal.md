# Proposal: Admin Stock Overview

## Intent

An admin browsing `/admin/products` cannot see stock at all. Answering "what is
running low?" means opening every product detail page one at a time — the
catalog-wide question has no catalog-wide answer. `GET /admin/products/{id}/stock`
already exists but loops `quantity_on_hand` per variant (N+1) for a single
product, so it cannot be scaled up as-is. Put current stock where admins already
browse, backed by one bulk read.

## Scope

### In Scope

- New bulk stock-read capability returning `dict[UUID, int]` (variant_id →
  current quantity) for all variants in **one** aggregate query.
- `PostgresStockLevelReader` gains the bulk method; `InMemoryStockLevelReader`
  gains it in lockstep.
- `list_admin_products` composes the bulk reader with
  `PostgresProductRepository.list_all()`; `AdminProductResponse` variants carry
  their own stock quantity.
- `frontend/src/app/(admin)/admin/products/page.tsx` renders per-variant stock.

### Out of Scope

| Deferred | Rationale |
|---|---|
| Dedicated `/admin/stock` page | Needs new route + proxy + page; the bulk port this change builds unblocks it later. |
| Low-stock threshold, alerts, sorting, filtering | No `searchParams`/sort/filter infra exists on any admin page; a real slice of its own. |
| Summed per-product totals | Locked: per-variant only. |
| Fixing `GET /admin/products/{id}/stock`'s N+1 | Untouched; still correct for one product. |
| Any Supabase migration, schema, view, index or trigger change | `variant_stock_levels` plus `stock_movements(variant_id) INCLUDE (quantity_delta)` already make this an index-only scan. **No migration.** |

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `admin-stock-management`: adds a bulk, catalog-wide current-stock read
  alongside the existing per-product one, and its list presentation.
- `admin-api-access`: `GET /admin/products` response now carries per-variant
  current stock.
- `admin-product-management`: the admin product list surfaces per-variant stock.

## Approach

Exploration Option 1. Mirror `StockMovementHistoryReader`'s precedent: an
isolated read capability on the `stock` side, consumed by the route. The adapter
runs a single `SELECT variant_id, quantity FROM variant_stock_levels` (optionally
`WHERE variant_id = ANY($1)`), materialized into a dict — **never** a loop over
`quantity_on_hand`. The route zips it onto the already-bulk `list_all()` result;
a variant with no movements resolves to `0`, not a missing key.

### Locked Decisions

| # | Decision |
|---|----------|
| D1 | **Per-variant** quantities. No summed per-product total. |
| D2 | Stock is added to the **existing** `GET /admin/products` response — no new endpoint, no new frontend proxy route, one request. |
| D3 | Single bulk aggregate query. Reproducing the N+1 of `get_admin_product_stock` is a defect, not an implementation choice. |
| D4 | Legal dependency direction stays `stock → products`. This is convention/docstring only — `test_domain_boundary.py` bans framework imports in `domain/`, it does **not** enforce direction. Do not claim otherwise. |

Confirmed by the user on 2026-08-16 via AskUserQuestion. D1–D4 must not be
reopened by `sdd-spec` or `sdd-design`.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `backend/src/gcell/stock/application/stock_level_reader.py` | Modified/New sibling | Bulk `dict[UUID, int]` port |
| `backend/src/gcell/stock/infrastructure/postgres_stock_level_reader.py` | Modified | Single aggregate query |
| `backend/src/gcell/stock/infrastructure/in_memory_stock_level_reader.py` | Modified | Same method, test parity |
| `backend/src/gcell/api/admin.py` | Modified | `list_admin_products` composition + response field |
| `frontend/src/app/(admin)/admin/products/page.tsx` | Modified | Per-variant stock column/badge |
| `supabase/migrations/`, `backend/src/gcell/stock/domain/**` | **Unchanged** | No migration, no domain change |
| `backend/tests/integration/api/test_admin_products.py`, `.../db/` | Modified | Route + adapter coverage |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Bulk method implemented as a loop over `quantity_on_hand` | Medium | D3; a test asserting one query / bounded round-trips |
| `InMemoryStockLevelReader` drifts, tests silently pass | Medium | Protocol conformance is checked; add the method in the same commit |
| `list_admin_products` payload grows for large catalogs | Low | One int per variant; the list is already unpaginated today |
| Direction `products → stock` creeps in unnoticed | Low | Nothing in CI catches it (D4) — enforce by review; compose in the route, not in `products` |
| 1200-line review budget | Low | Backend + frontend in one slice; `sdd-tasks` makes the slicing call |

## Rollback Plan

Single-commit revert. No migration, no schema change, no data written, no write
path touched — the change is read-only end to end. Reverting restores the prior
`AdminProductResponse` shape; the frontend column disappears with it.

## Dependencies

- `admin-stock-management`, `admin-stock-movement-history`,
  `admin-initial-stock-seeding` — all shipped and archived. Nothing blocking.

## Success Criteria

- [ ] `GET /admin/products` returns a current quantity for every variant in one
      request, and the admin list renders it.
- [ ] Serving the whole catalog issues one stock query regardless of variant count.
- [ ] A variant with zero movements reports `0`, not `null` and not a missing key.
- [ ] `InMemoryStockLevelReader` implements the same method; existing stock tests
      pass unmodified.
- [ ] `supabase/migrations/` is unchanged.
- [ ] `GET /admin/products/{id}/stock` and every write path behave exactly as before.

## Proposal question round — Confirmed by the user on 2026-08-16 via AskUserQuestion

| # | Question | Decision |
|---|----------|---------------------|
| D5 | Zero-stock presentation on the list? | **Confirmed: reuse the existing detail-page treatment.** `admin-stock-management`'s "Zero-Stock Variants Are Visually Distinguished" convention now also applies to the list, keeping both admin surfaces consistent. |
| D6 | Failure behavior if the bulk stock read fails but products load? | **Confirmed: fail the whole request.** Stock is part of the response contract, not an optional decoration — a blank/omitted stock value would render as misleading. |
| D7 | `AdminProductResponse` is shared by list/GET-by-id/POST/PATCH. Does stock go only on the list, or on all four? (Surfaced by `sdd-design`, since a required stock field on the shared model forces a fabricated `0` or extra reads on write paths.) | **Confirmed: list only.** New list-only response models (`AdminProductListItemResponse`); POST/PATCH/GET-by-id stay exactly as they are today. Not a D2 deviation — the wire response of `GET /admin/products` still gains the field. |

Both recommended defaults, plus D7, were accepted as-is. D1–D7 are now locked
and must not be reopened by `sdd-spec`, `sdd-design`, or `sdd-tasks`.
