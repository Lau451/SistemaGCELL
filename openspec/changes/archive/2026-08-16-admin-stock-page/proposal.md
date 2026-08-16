# Proposal: Admin Stock Page

## Intent

`admin-stock-overview` put per-variant stock on `/admin/products`, but the
catalog-wide question "what do I restock first?" still has no answer: quantities
are buried inside per-product groups, in catalog order, so an admin must scan
every product to find the few variants that are nearly out. This change adds the
dedicated `/admin/stock` page that change explicitly deferred — a flat,
quantity-ascending, per-variant triage list with text search — reusing the bulk
read port that change already shipped.

## Scope

### In Scope

- New `GET /admin/stock`: composes `PostgresProductRepository.list_all()` with
  the **existing** `PostgresStockLevelReader.quantities_for_variants()`, exactly
  as `list_admin_products` already does.
- Flat, one-row-per-variant response carrying product context (name, slug) —
  `ProductVariant` has no back-reference, so the route attaches it. New
  list-only response model(s); `AdminProductList*Response` stay untouched.
- Server-side sort: quantity ascending, most critical first. No hardcoded
  threshold.
- Optional `?below=N` filter and optional text search over product name and
  variant color.
- New proxy `frontend/src/app/api/admin/stock/route.ts` (`adminBackendFetch`),
  forwarding the query params.
- New `frontend/src/app/(admin)/admin/stock/page.tsx` — first admin page reading
  `searchParams` — reusing the `text-destructive` / "Out of stock" convention.
- Nav link in `admin/layout.tsx` beside "Products".

### Out of Scope

| Deferred | Rationale |
|---|---|
| Pagination | `list_all()` is unpaginated today; matching that precedent. Known, accepted limitation — not a defect. |
| Any Supabase migration/schema/view/index/trigger change | `variant_stock_levels` + existing index already suffice. **No migration.** |
| Low-stock email/notification alerts | In-page visual triage only; no alerting mechanism. |
| Editing stock from this page | Read-only, same as `admin-stock-overview`. |
| A general `?sort=` multi-column param | Quantity-ascending is the only ordering this page needs. |

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `admin-api-access`: new `GET /admin/stock` endpoint on the admin router, with
  its query params and admin-auth requirement.
- `admin-stock-management`: catalog-wide flat triage view — ascending ordering,
  optional threshold, optional search, zero-stock treatment.

## Approach

Exploration Option (c), plus search. No new port, no new adapter, no domain
change: the bulk reader's totality contract (every requested id present, `0` for
zero-movement variants) is already exactly what a triage list needs. The route
flattens products into variant rows, attaches product name/slug, applies filters,
sorts ascending, and returns. Composition lives in `api/admin.py`, never inside
`products/`.

### Locked Decisions

| # | Decision |
|---|----------|
| D1 | **No fixed default threshold.** Every variant is listed, sorted ascending by quantity. `?below=N` narrows further and is purely optional. |
| D2 | **Text search ships in this first version**, matching product name and/or variant color — chosen over the sort-only MVP. |
| D3 | **Sorting is server-side.** A large catalog must not ship an unsorted payload for the client to sort. |
| D4 | **Flat per-variant rows**, not grouped by product; each row carries product context. New list-only response models — do not widen `AdminProductResponse` or the `AdminProductList*` models. |
| D5 | Query params are **clamped in application code** (`ListVariantStockMovementsUseCase`'s `max(1, min(...))` precedent), not rejected via FastAPI `Query()` validation. |
| D6 | Route mirrors `list_admin_products`: **no `_execute_or_raise`**; a read failure propagates to FastAPI's default 500. |
| D7 | Legal dependency direction stays `stock → products`. Convention/docstring only — `test_domain_boundary.py` bans framework imports in `domain/`, it does **not** enforce direction. Do not claim otherwise. |
| D8 | Search is **case-insensitive substring** matching (an admin typing "iph" or "neg" expects hits), not exact/prefix. |
| D9 | Search is **one box** matching against product name OR variant color — not two separate fields. |
| D10 | `?below=N` and search **combine with AND** — both conditions must match, filters narrow rather than widen. |
| D11 | `?below=0` is **valid and meaningful** ("show only out-of-stock"), not clamped to a minimum of 1. |
| D12 | **Empty state has distinct copy**: "no variants match your search/filter" reads differently from "catalog has no variants at all" — a typo in a search box must never look like data loss. |
| D13 | **Each row links to `/admin/products/{product_id}`** — surfaced by `sdd-design`, confirmed by the user via AskUserQuestion. Triage-then-act: an admin who spots a critical row goes straight to the product, no manual search on `/admin/products`. |

D1–D2 confirmed by the user on 2026-08-16 via AskUserQuestion. D8–D11 confirmed
by the user on 2026-08-16 via AskUserQuestion (Q1, Q2, Q3, Q5 respectively). D12
(Q4, empty-state copy) is resolved as its own recommended default — UI-polish,
not a product fork; `sdd-design` must still specify the exact copy strings.
D1–D13 must not be reopened by `sdd-spec`, `sdd-design`, or `sdd-tasks`.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `backend/src/gcell/api/admin.py` | Modified | New route + new flat response model(s) |
| `backend/src/gcell/stock/**`, `backend/src/gcell/products/**` | **Unchanged** | Ports, adapters and domain reused as-is |
| `frontend/src/app/api/admin/stock/route.ts` | New | Proxy forwarding `below` / search params |
| `frontend/src/app/(admin)/admin/stock/page.tsx` | New | `searchParams` Server Component |
| `frontend/src/app/(admin)/admin/layout.tsx` | Modified | Nav link |
| `supabase/migrations/` | **Unchanged** | No migration |
| `backend/tests/integration/api/`, frontend tests | Modified/New | Route + page coverage |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Review workload — new route + model + proxy + page + search is larger than `admin-stock-overview` | **High** | Do not assume a single PR. `sdd-tasks` must forecast against the 1200-line budget and slice backend / frontend if needed (`ask-on-risk`). |
| Search implemented per-request in Python over the full catalog degrades at scale | Medium | Decide the matching layer during design; unpaginated `list_all()` is already the ceiling here |
| Unpaginated payload grows with catalog size | Medium | Accepted for MVP (Out of Scope); flagged as a known limitation, revisit with pagination |
| First `searchParams` admin page invents an ad-hoc convention | Medium | Establish it deliberately in design; later admin pages must reuse it |
| Shared response models get widened instead of new flat ones | Medium | D4; enforce by review |
| Direction `products → stock` creeps in unnoticed | Low | Nothing in CI catches it (D7) — compose in the route, enforce by review |

## Rollback Plan

Single-commit revert. No migration, no schema change, no write path touched, no
existing endpoint's contract altered — the change is additive and read-only end
to end. Reverting removes the route, proxy, page and nav link; `/admin/products`
is unaffected.

## Dependencies

- `admin-stock-overview` (archived 2026-08-16) — supplies
  `CatalogStockLevelsReader.quantities_for_variants()`. Shipped; nothing blocking.

## Success Criteria

- [ ] `GET /admin/stock` returns one row per variant with product name/slug and
      current quantity, sorted ascending by quantity, in one bulk stock query.
- [ ] `?below=N` narrows the list; omitting it returns the full catalog with no
      implicit threshold.
- [ ] Text search matches product name and variant color and combines with
      `?below=N`.
- [ ] A variant with zero movements reports `0` and renders with the existing
      zero-stock treatment.
- [ ] `/admin/stock` is reachable from the admin nav.
- [ ] `supabase/migrations/`, `stock/**` and `products/**` are unchanged; every
      existing endpoint behaves exactly as before.

## Proposal question round — Confirmed by the user on 2026-08-16 via AskUserQuestion

| # | Question | Decision |
|---|----------|---------------------|
| Q1 (→D8) | Search matching semantics: case-insensitive **partial/substring** match, or exact/prefix only? | **Confirmed: case-insensitive substring.** |
| Q2 (→D9) | Does search span product name **and** variant color in one box, or two separate fields? | **Confirmed: one box, matches either field.** |
| Q3 (→D10) | Do `?below=N` and search **AND** together (both must match) or OR? | **Confirmed: AND.** |
| Q5 (→D11) | Is `?below=0` meaningful (show only out-of-stock), or should it clamp to `1` like the movements-limit precedent? | **Confirmed: allow `0`.** |
| Q4 (→D12) | Should "no variants match your search/filter" read differently from "catalog is empty"? | **Resolved as recommended default: yes, distinct copy** — UI-polish, not a product fork. |

All recommended defaults were accepted as-is. D12 is locked alongside D1-D11.
