# Proposal: Admin Low-Stock Alerts

## Intent

`/admin/stock` answers "what do I restock first?" only once the admin decides to
go look. Nothing today tells them there is anything to look at — the panel is
entirely passive, so a variant can sit at zero until a customer surfaces it. This
change adds the smallest genuinely proactive signal: a low-stock count badge on
the admin nav, visible from any `/admin/*` page, reusing 100% of the read path
`admin-stock-page` already shipped.

## Scope

### In Scope

- A count badge on the "Stock" nav link in `admin/layout.tsx` (e.g. `Stock (3)`)
  showing how many variants sit at or below the threshold.
- Threshold is a **fixed `below=5`**, inclusive (`quantity <= 5`), matching the
  existing route's inclusive `?below=N` semantics.
- Reuse of the existing `GET /admin/stock?below=5`, `ListCatalogStockLevelsUseCase`
  and `CatalogStockLevelsReader.quantities_for_variants()` as-is.

### Out of Scope

| Deferred | Rationale |
|---|---|
| Email digests / push notifications | Repo grep confirms **zero** email infra (`backend/pyproject.toml` has no email SDK; `supabase/config.toml` SMTP is Auth-only). Building it is a separately-scoped change. |
| Cron / scheduler / queue | Grep confirms zero scheduler, no `pg_cron`, no `BackgroundTasks`. Same reasoning. |
| Admin-configurable threshold | Fixed `5` for the first slice. |
| Badge on the `/admin` landing page | That page is deliberately "no dashboard widgets"; reopening it is its own decision. |
| Any Supabase migration/schema/view/index change | **No migration.** Read-only over existing data. |
| Any Gemini API usage | None introduced. |
| Editing stock from the badge | Badge links to `/admin/stock`; no write path. |

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `admin-stock-management`: passive low-stock indicator on the admin shell — the
  fixed inclusive `<= 5` threshold, the count's meaning, and zero-count behavior.
- `admin-api-access`: **not needed.** OQ1 resolved toward reusing
  `GET /admin/stock?below=5` unchanged (D5) — no count-only endpoint, no delta.

## Approach

Exploration Option 1. The Server Component `admin/layout.tsx` obtains a low-stock
count and renders it beside the existing "Stock" link. No new port, no new
adapter, no domain change, and — pending OQ1 — no backend file touched at all.

### Locked Decisions

| # | Decision |
|---|----------|
| D1 | **In-app badge only.** No email, no push, no scheduler infrastructure in this change. |
| D2 | **Fixed threshold `below=5`, inclusive.** Not admin-configurable, not `below=0`-only. This is a *badge* default and does **not** reverse `admin-stock-page`'s D1, which governs the triage *page's* list rendering (no implicit filter there). Both stand. |
| D3 | Reuse the shipped read path (`ListCatalogStockLevelsUseCase` / `quantities_for_variants()`). No new port or adapter. |
| D4 | The badge is an **entry point**, not a second triage surface: clicking it goes to `/admin/stock`. |
| D5 | **Count computed in `layout.tsx`** on every `/admin/*` page load, calling the existing `GET /admin/stock?below=5` unchanged. No count-only backend endpoint. The extra round trip is accepted (single-admin, low-traffic system). |
| D6 | **Badge hides entirely at count `0`.** No `Stock (0)` state — standard notification-badge convention, no permanent visual noise. |
| D7 | Non-zero counts reuse the existing `text-destructive` convention already used for zero-stock rows elsewhere in the admin (visual consistency, not a new convention). |
| D8 | The count is **exact**, not capped/qualitative — the catalog is small enough that staleness between render and click-through is a non-issue at this scale. |

D1–D2 confirmed by the user on 2026-08-16 via AskUserQuestion. D5–D6 confirmed
by the user on 2026-08-16 via AskUserQuestion. D7–D8 resolved as recommended
defaults (UI-polish, not product forks) — `sdd-design` should still specify
exact styling. D1–D8 must not be reopened by `sdd-spec`, `sdd-design`, or
`sdd-tasks`.

### Hexagonal Note

The `stock -> products` direction rule (`admin-stock-page` D7 — convention and
docstring only, **not** enforced by `test_domain_boundary.py`) is stated here for
continuity but is **likely inapplicable**: this change is expected to touch zero
backend files. It becomes relevant only if OQ1 resolves toward a backend change.

## Open Questions

None. All four (OQ1–OQ4) are resolved and locked as D5–D8 above — see that table
for the confirmed answer to each.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `frontend/src/app/(admin)/admin/layout.tsx` | Modified | Nav badge + count fetch |
| `frontend/src/app/api/admin/stock/route.ts` | **Unchanged** | Already forwards `below` (D5) |
| `backend/src/gcell/**` | **Unchanged** | Route, use case and reader reused as-is (D5) |
| `frontend/src/app/(admin)/admin/page.tsx` | **Unchanged** | Landing page stays widget-free |
| `supabase/migrations/` | **Unchanged** | No migration |
| frontend tests | New | Layout badge coverage |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Unconditional DB round trip added to every `/admin/*` page | Accepted | D5 — negligible cost at this scale, no caching needed for a single-admin system |
| Fixed `5` reads as reversing `admin-stock-page` D1 | Medium | D2 states the distinction explicitly; `sdd-spec` must preserve the page's no-implicit-threshold requirement untouched |
| Count is stale relative to concurrent stock movements | Low | Inherent to any server-rendered count; OQ4 decides whether exactness is even claimed |
| Scope creep back toward email/scheduler | Low | D1 + Out of Scope table |

## Rollback Plan

Single-commit revert. Additive, read-only, frontend-only (pending OQ1): no
migration, no schema change, no write path, no existing endpoint contract
altered. Reverting removes the badge; `/admin/stock` and `/admin/products` are
unaffected.

## Dependencies

- `admin-stock-page` (archived 2026-08-16) — supplies `GET /admin/stock?below=N`
  and `ListCatalogStockLevelsUseCase`. Shipped; nothing blocking.
- `admin-stock-overview` (archived 2026-08-16) — supplies
  `quantities_for_variants()`. Shipped; nothing blocking.

## Delivery Forecast

**Small.** One modified frontend file plus tests, reusing the entire backend read
path. `sdd-tasks` should expect this to land well under the 1200-line review
budget as a **single PR** — do not assume chained PRs merely because recent
changes needed them. Re-forecast only if OQ1 resolves toward a backend change.

## Success Criteria

- [ ] The admin nav shows a low-stock count on the "Stock" link from every
      `/admin/*` page.
- [ ] The count equals the number of variants with `quantity <= 5`, using the
      existing bulk stock read (no new query path).
- [ ] Clicking the badge/link reaches `/admin/stock`.
- [ ] `/admin` landing, `supabase/migrations/`, `stock/**` and `products/**` are
      unchanged; every existing endpoint behaves exactly as before.
- [ ] The badge is hidden entirely when the count is `0` (D6).
