# Proposal: Admin Stock Movement Date Filter

## Intent

The per-variant movement history is an unfiltered, newest-first, keyset-paginated
list. To answer "what moved this week?" the admin must click "Load more" until
the dates scroll past — the list has no way to narrow a time window. This change
adds an optional `?since`/`?until` date filter to the existing movement-history
endpoint plus a date-range UI with three quick presets, so a bounded question
takes one interaction instead of repeated pagination.

**Scope expanded mid-cycle (D14):** `sdd-design` discovered the product detail
page has no variant switcher at all — `[id]/page.tsx` hardwires
`variantId={product.variants[0].id}`, so the movement history (and now the date
filter) is only ever visible for a product's *first* variant. The user confirmed
via AskUserQuestion on 2026-08-16 that building the switcher now, alongside the
date filter, is in scope for this change rather than deferred.

**This reverses a locked, merged-spec decision.** `admin-stock-management`'s
`Admin Views Per-Variant Movement History` requirement currently states the view
"MUST NOT expose any filter by movement type or date range". The **date-range
half is reversed deliberately, at the user's explicit request in this session**
— not silently overwritten. The **movement-type half and the "no running/
resulting balance" clause stay locked and untouched.**

## Scope

### In Scope

- Optional `?since` / `?until` query parameters on the existing
  `GET /admin/products/{product_id}/variants/{variant_id}/stock/movements`,
  filtering `stock_movements.created_at` alongside the existing `variant_id` +
  `before_id` keyset predicate.
- `since` / `until` validated & clamped **in application code**
  (`ListVariantStockMovementsUseCase`), the same idiom as `limit`'s existing
  clamp — never raw FastAPI `Query()` validation.
- Proxy allowlist extended by exactly two entries (`since`, `until`).
- Frontend: date-range inputs plus **three preset buttons** (today / last 7 days
  / last 30 days) on the history view.
- **A variant switcher on the product detail page** (D14) — URL-driven
  (`?variant=<id>`), consistent with the URL-driven date-filter architecture
  design already established, so the two features share one state model instead
  of colliding. Switching variants preserves the active date filter (D12).
- Explicit `MODIFIED Requirements` deltas for **both** affected specs, plus a
  requirement covering the variant switcher (capability TBD by `sdd-spec` —
  likely `admin-product-management` or `admin-stock-management`).

### Out of Scope

| Deferred | Rationale |
|---|---|
| Filter by **movement type** | Not requested. The MUST NOT clause for type filtering **stays locked and unchanged**. |
| Running / resulting balance per row | The other half of the same MUST NOT clause — **stays locked**, unrelated to this change. |
| Any Supabase migration / schema / index change | **No migration.** `created_at` already exists and is already read into `RecordedStockMovement`. |
| A `created_at` index | The existing covering index does not order by `created_at`, so a range predicate forces heap fetches. **Accepted tradeoff**, per the original design's small-row-count reasoning — a revisit-if-measured-slow item, **not a defect**. |
| Domain-layer change | None. `RecordedStockMovement` stays the application read model. |
| Any Gemini API usage | None introduced. |
| Saved / named filters, CSV export | Not requested. |

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `admin-stock-management`: `Admin Views Per-Variant Movement History` — reverses
  **only** the date-range half of the MUST NOT clause; adds date-filter and
  preset behavior. The type-filter and no-balance clauses must be carried through
  **verbatim and unchanged**.
- `admin-api-access`: `Variant Stock Movement History Endpoint` — extends the
  locked `limit`/`before_id`-only query-parameter contract with optional
  `since`/`until`, including their clamp/validation semantics.

## Approach

Exploration Approach 1 (SQL-level `since`/`until` predicate on the existing
route) with Approach 2's presets folded in — presets are pure client-side date
math that compute `since`/`until` and submit, adding **zero** backend surface.
No new endpoint, no new port, no new adapter, no migration.

### Locked Decisions

| # | Decision |
|---|----------|
| D1 | **Extend the existing route** with optional `?since`/`?until` filtering `created_at`. No new endpoint. |
| D2 | **Presets ship in this change**, not as a fast-follow: today / last 7 days / last 30 days, alongside the plain since/until inputs. Client-side date math only. |
| D3 | This is a **deliberate, user-requested reversal** of the date-range half of a merged MUST NOT clause — recorded as an explicit `MODIFIED Requirements` delta, never a silent overwrite. |
| D4 | The **"no running/resulting balance"** clause is **unchanged and stays locked**. Do not touch it. |
| D5 | **Movement-type filtering stays out of scope**; its MUST NOT stays locked. |
| D6 | `since`/`until` are **validated/clamped in application code** (use case), mirroring `limit`'s clamp precedent — not raw FastAPI `Query()` validation. |
| D7 | Both params are **optional**. Omitting both preserves today's exact behavior (full unfiltered history) — backward compatible. An inverted range (`since` later than `until`) is rejected with **422** (D10) — a deliberate, application-code-raised validation error, not FastAPI's declarative `Query()` mechanism (still consistent with D6: the check runs inside the use case, not a `Query(...)` constraint). |
| D8 | **No Supabase migration/schema/index change.** Unindexed range predicate accepted (see Out of Scope). |
| D9 | Proxy forwards `since`/`until` via a **fresh `URLSearchParams` allowlist**, never `request.url.search` verbatim (reuses movement-history Decision 7). |

D1–D2 confirmed by the user on 2026-08-16 via AskUserQuestion. D3–D9 follow
directly from that scope plus existing repo conventions. D1–D13 (see D10–D13
below) must not be reopened by `sdd-spec`, `sdd-design`, or `sdd-tasks`.

### Deferred to Design — must be decided **explicitly**, not silently picked

| # | Decision `sdd-design` owns |
|---|---|
| DD1 | **Timezone convention.** `created_at` is `timestamptz`; UI inputs are date-only. Whether `since`/`until` mean UTC day boundaries or browser-local day boundaries must be an explicit, documented convention. |
| DD2 | **Stale-keyset-cursor-on-filter-change.** URL/`searchParams`-driven refetch (reuses movement-history Decision 6's reset-on-new-prop-reference) vs. a new client-side self-reset — **and** how that interacts with the currently **client-driven** variant switcher on the product detail page. That inconsistency pre-exists this change; design must resolve it deliberately rather than let this change pick a side by accident. |

### Hexagonal Note

Same `stock -> products` direction rule — **convention and docstring only, not
enforced by `test_domain_boundary.py`**. No domain change, no migration.

## Open Questions

None. OQ1–OQ4 are resolved and locked as D10–D13 below.

| # | Decision |
|---|----------|
| D10 | **Inverted range is a 422 validation error**, not an empty-list clamp. `since` later than `until` is rejected explicitly before any query runs — the user chose this over the recommended "clamp, never reject" default. |
| D11 | `until` is **inclusive of the whole selected day** — a date-only `until` reads as "through the end of that day" (pairs with, but is distinct from, DD1's timezone convention). |
| D12 | The active filter **persists** when the admin switches to another variant on the same product page. |
| D13 | The empty state has **distinct copy** for "no movements in this range" vs. "this variant has no history at all". |

Confirmed by the user on 2026-08-16 via AskUserQuestion. D10–D13 must not be
reopened by `sdd-spec`, `sdd-design`, or `sdd-tasks`.

| # | Decision |
|---|----------|
| D14 | **Build the variant switcher now**, in this change, not deferred. Surfaced by `sdd-design`'s discovery that no switcher exists in shipped code (the product detail page hardwires the first variant). URL-driven (`?variant=<id>`), matching the date filter's existing URL-driven architecture (DD2) so the two features share one state model. |
| D15 | **"Last 7 days" = today plus 6 days back (7 calendar days total, inclusive of today).** Same convention for "last 30 days" (today plus 29 days back). |

| D16 | **`StockManager`'s record-movement variant `<select>` stays independent** from `?variant=` — no pre-selection, no coupling. Surfaced by `sdd-design`'s DD3: avoids discarding in-progress quantity/reason input when the admin switches which variant's history they're viewing. |

D14–D16 confirmed by the user on 2026-08-16 via AskUserQuestion. D1–D16 must not
be reopened by `sdd-spec`, `sdd-design`, or `sdd-tasks`.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `backend/src/gcell/api/admin.py` | Modified | Accept + pass through `since`/`until` |
| `backend/src/gcell/stock/application/list_variant_stock_movements.py` | Modified | Validate/clamp `since`/`until` (D6) |
| `backend/src/gcell/stock/infrastructure/postgres_stock_movement_history_reader.py` | Modified | `created_at` range predicate in the SQL |
| `frontend/src/app/api/admin/products/[id]/variants/[variantId]/stock/movements/route.ts` | Modified | Allowlist grows by `since`/`until` (D9) |
| `frontend/src/app/(admin)/admin/products/stock-history.tsx` | Modified | Date inputs + 3 presets + reset-on-filter-change (shape per DD2) |
| `frontend/src/app/(admin)/admin/products/[id]/page.tsx` | Possibly Modified | Only if DD2 resolves toward `searchParams` |
| `backend/src/gcell/**/domain/**` | **Unchanged** | No domain change |
| `supabase/migrations/` | **Unchanged** | **No migration** (D8) |
| backend + frontend tests | New/Modified | Filter, clamp, preset, and reset coverage |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Spec reversal reads as a silent overwrite of a locked requirement | Medium | D3 + explicit `MODIFIED Requirements` deltas in **both** specs; D4/D5 carry the untouched clauses through verbatim |
| Stale `before_id` cursor sent with a changed filter — results are SQL-correct but look broken | **High if unaddressed** | DD2 must be resolved explicitly; Decision 6 precedent exists and must be re-applied, not assumed |
| Ambiguous timezone semantics produce off-by-one-day results | Medium | DD1 forces an explicit, documented convention plus tests |
| Unindexed `created_at` range forces heap fetches | Low | Accepted per D8/original row-count reasoning; revisit with an index only if measured slow |
| Preset UI + filter state inflates the frontend diff | Medium | `sdd-tasks` must produce a genuine forecast; backend/frontend is a natural slice boundary |

## Rollback Plan

Single-commit revert. Purely additive and read-only: no migration, no schema
change, no write path, and both new params are optional (D7), so reverting
restores the exact previous endpoint behavior. The spec deltas revert with the
same commit, restoring the original MUST NOT clause. `/admin/stock` and
`/admin/products` are otherwise unaffected.

## Dependencies

- `admin-stock-movement-history` (archived 2026-08-15) — supplies the route, use
  case, reader, proxy allowlist pattern (Decision 7) and the reset-on-new-prop
  mechanism (Decision 6). Shipped; nothing blocking.
- OQ1–OQ4 should be answered before `sdd-spec` writes scenarios.

## Delivery Forecast

**Medium-to-High**, revised upward after D14. Backend remains a pure edit-existing
slice (no new files). Frontend now covers date inputs, three presets,
reset-on-filter-change, AND a genuinely new variant switcher UI (`?variant=`
routing, switcher component, `[id]/page.tsx` reading the variant from
`searchParams` instead of hardcoding the first one) — real new surface, not just
an edit. `sdd-tasks` MUST produce a genuine forecast and should seriously
consider chaining (backend + date-filter spec deltas first, variant switcher +
combined frontend second) rather than assuming a single PR.

## Success Criteria

- [ ] The movement-history endpoint accepts optional `since`/`until`, filtering
      `created_at`, correctly combined with the existing keyset predicate.
- [ ] An inverted range (`since` > `until`) is rejected with 422, raised from
      application code, not FastAPI's declarative `Query()` validation (D6, D10).
- [ ] Omitting both params reproduces today's behavior byte-for-byte (D7).
- [ ] The history view offers a date range plus today / last 7 days / last 30
      days presets, and a filter change never returns stale-cursor results.
- [ ] Both spec deltas land, with the movement-type and no-balance clauses
      carried through **unchanged** (D4, D5).
- [ ] `supabase/migrations/` and every domain module are unchanged; all other
      admin endpoints behave exactly as before.
