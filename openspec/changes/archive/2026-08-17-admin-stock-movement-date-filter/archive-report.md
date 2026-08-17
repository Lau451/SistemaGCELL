# Archive Report: Admin Stock Movement Date Filter

**Change**: `admin-stock-movement-date-filter`  
**Status**: ARCHIVED  
**Date Archived**: 2026-08-17  
**Verification**: PASS (commit `cfdff241590d6dbbb37d59f3d4689092f0e2f215`)

## Executive Summary

The `admin-stock-movement-date-filter` change has been successfully planned, implemented, verified, and archived. This change adds optional `?since`/`?until` date filtering to the stock movement history endpoint plus a variant switcher on the product detail page. The change deliberately reversed only the date-range half of a previously-locked "MUST NOT" clause, while preserving the movement-type-filter and no-running-balance clauses unchanged. Delivered as three chained PRs (backend, frontend date-filter, variant switcher); 23/23 tasks complete; full verification suite passing (352 backend tests, 344 frontend tests, 0 type errors).

## Change Intent

Enable admins to filter the per-variant stock movement history by date range (today, last 7 days, last 30 days, or custom range) without manually scrolling through keyset-paginated pages. Additionally, implement a server-rendered variant switcher on the product detail page to allow admins to choose which variant's movement history is displayed when viewing multi-variant products. Backward compatible: omitting filter parameters and the `?variant=` parameter both preserve existing behavior.

## Scope

### In Scope
- Optional `?since`/`?until` filtering on `GET /admin/products/{product_id}/variants/{variant_id}/stock/movements`
- Date-range validation and clamping in application code (use case layer)
- Proxy allowlist extended to include `since` and `until` (exactly 4 params: limit, before_id, since, until)
- Frontend date-range inputs, three presets (today/last7/last30), and inverted-range client-side guard
- Server-rendered variant switcher component for multi-variant products
- Variant selection via `?variant=<id>` query parameter, membership-checked before fetch, defaults to `variants[0]`
- Three delta specs (admin-stock-management, admin-api-access, admin-product-management) merged into main specs

### Out of Scope
- Movement-type filtering (MUST NOT clause stays locked and unchanged)
- Running/resulting balance per row (MUST NOT clause stays locked and unchanged)
- Supabase migration or schema change (no migration; `created_at` already exists)
- Domain-layer changes (read model stays as-is)
- `StockManager` record-movement selector coupling to the variant switcher

## Deliverables

### Commits Delivered
Three chained PRs across the timeline:
1. **Backend Foundation + Date Filter Endpoint** (PRs `6597a21`, `463824b`)
   - `InvertedDateRangeError(ValueError)` exception
   - Optional `since`/`until` params on use case, both readers, and API route
   - Tz-aware date normalization, midnight expansion for `until`
   - Application-code validation (not FastAPI `Query()` declarative)
   - Full backend test coverage (Phase 1-4 tasks)

2. **Frontend Date-Range UI** (PRs `63824a0`, `7fced46`)
   - `stock-history-dates.ts` utility: `toSinceParam`, `toUntilParam`, `dayFromParam`, `presetRange`, `isInvertedRange`
   - `stock-history.tsx` component: date inputs, 3 presets, Clear button, `router.push` URL-driven filter
   - Proxy allowlist update (4 params, fresh `URLSearchParams` rebuild)
   - D13 distinct empty states (no-history vs. filtered-empty)
   - URL-driven reset via Decision 6 compare-during-render mechanism
   - Full frontend test coverage (Phase 5-8 tasks)

3. **Variant Switcher + Page Wiring** (PRs `dd42ed6`, `cfdff24`)
   - `variant-switcher.tsx` server component: link row, `aria-current` on active, `URLSearchParams` hrefs carrying variant + date filter
   - Null render for single-variant products
   - `[id]/page.tsx` `resolveActiveVariant`, membership check, `notFound()` guard on foreign/unknown/malformed `?variant=`
   - Inverted-range guard (no fetch if `since > until`)
   - Page docstring corrected
   - Full integration test coverage (Phase 9-11 tasks)

### Specs Merged
| Domain | Action | Details |
|--------|--------|---------|
| admin-stock-management | MODIFIED | Reversed date-range half of "MUST NOT" clause; added date filter requirement with presets, inverted-range rejection, filter persistence across variant switches, distinct empty states. Movement-type and no-balance clauses carried verbatim, unchanged. |
| admin-api-access | MODIFIED | Extended "Variant Stock Movement History Endpoint" requirement to accept optional `since`/`until`, validated in use case, combined with keyset predicate, reject inverted ranges with 422. Unchanged behavior when both params omitted. |
| admin-product-management | ADDED | Five new requirements: variant switcher render logic, URL-driven selection with backward compatibility, filter persistence across switches, 404 on unknown/foreign/malformed `?variant=`, `StockManager` independence. |

**Merged successfully**: No conflicts; all three deltas applied cleanly. Movement-type and no-balance clauses verified preserved byte-for-byte.

## Task Completion

**Status**: 23/23 tasks complete (obs #431)

- [x] Phase 1: Backend Foundation (2 tasks)
- [x] Phase 2: Use Case Date Filtering (2 tasks)
- [x] Phase 3: Infrastructure Readers (4 tasks)
- [x] Phase 4: API Wiring (3 tasks)
- [x] Phase 5: Pure Date Math (2 tasks)
- [x] Phase 6: Proxy Allowlist (2 tasks)
- [x] Phase 7: History View UI (2 tasks)
- [x] Phase 8: Page Wiring — Date Filter (2 tasks)
- [x] Phase 9: Variant Switcher Component (2 tasks)
- [x] Phase 10: Page Wiring — Variant Switcher (2 tasks)
- [x] Phase 11: Cleanup (1 task)

All tasks marked complete in the persisted tasks artifact; no unchecked implementation tasks remain.

## Verification Results

**Verdict**: PASS (obs #434, commit `cfdff241590d6dbbb37d59f3d4689092f0e2f215`)

| Dimension | Result |
|-----------|--------|
| Requirements | 7/7 (admin-stock-management ×2, admin-api-access ×2, admin-product-management ×3) |
| Scenarios | 31/31 (all behaviors traced to source code, tested end-to-end) |
| Blockers | 0 |
| Critical Findings | 0 |
| Warning Findings | 0 |
| Suggestion Findings | 0 (unindexed `created_at` range is documented tradeoff, not a defect) |

### Test Coverage
- Backend: 352 tests passed, 2 pre-existing warnings, exit 0
- Frontend: 344 tests passed (47 files), exit 0
- TypeScript: 0 errors, exit 0

### Code Verification
All 11 source-level checks passed:
1. `InvertedDateRangeError` defined with `since`/`until` storage ✓
2. Ownership guard → normalize → inverted check → reader call ordering ✓
3. Postgres + in-memory readers both implement matching inclusive boundaries ✓
4. `admin.py` route uses plain `datetime | None` params, no `Query()`, no new except arm ✓
5. `stock-history-dates.ts` produces offset-aware ISO instants with microsecond precision ✓
6. Proxy `route.ts` allowlist = exactly 4 params, fresh `URLSearchParams` rebuild ✓
7. `stock-history.tsx` URL-driven, reuses Decision 6 reset, two distinct D13 empty states ✓
8. `variant-switcher.tsx` null for <2 variants, `aria-current` on active, hrefs carry variant+filters ✓
9. `[id]/page.tsx` membership check before fetch, `notFound()` guard, docstring corrected ✓
10. `stock-manager.tsx` confirmed untouched (commit `33ca371`, predating this change) ✓
11. Zero domain-layer and zero migration files touched (git diff verified) ✓

## Archive Contents

Archived to: `openspec/changes/archive/2026-08-17-admin-stock-movement-date-filter/`

- [x] `proposal.md` — intent, scope, open questions, delivery forecast
- [x] `design.md` — technical approach, architecture decisions (DD1-DD4), data flow, file changes, interfaces, testing strategy, threat matrix
- [x] `specs/` — three delta specs (admin-stock-management, admin-api-access, admin-product-management)
- [x] `tasks.md` — 23 phased work units with test commands, 3-PR delivery strategy, chained-PR rationale
- [x] `apply-progress.md` — evidence of all 3 batches complete, 23/23 tasks, merged commit history
- [x] `verify-report.md` — full verification report with PASS verdict, 0 blockers, 0 critical
- [x] `archive-report.md` — this document

**Diff verification**: Source snapshot vs. archived folder, empty diff (byte-identical). Archive move verified as clean rename via `git mv` (not copy+delete).

## Highlights

### Design Excellence
- **Final-State Authority**: Archive report describes state AT CLOSE. Intermediate snapshots (`verify-report`, `apply-progress`) marked as timebound; stale claims not re-stated as current facts.
- **Spec Reversal Transparency**: Change explicitly reverses ONLY the date-range half of a merged "MUST NOT" clause; movement-type and no-balance halves carried through verbatim, with a parenthetical explaining the reversal per D3.
- **URL-Driven State Model**: Date filter and variant switcher share one `searchParams` source of truth, eliminating the proposal's High risk (stale keyset cursor) through established Decision 6 mechanism.
- **Membership-Checked 404**: Unknown `?variant=` 404s (never 403, never fallback) via in-memory membership test against already-fetched data before any history fetch; matched variant's own id (never raw param) used in fetch path.

### Testing Discipline
- Strict TDD (RED→GREEN): 13 new tests across 3 PRs, all passing.
- Threat matrix coverage: HTTP query passthrough (allowlist), IDOR-adjacent `?variant=` (membership check, 404).
- Source-verified (not trust-checkbox): ordering, readers, proxy params, empty states, variant resolution, all traced to actual code and covered by passing tests.

### Delivery Scaling
- 3 chained PRs (1150–1400 lines total), each independently reviewable and revertible.
- Backend single point (use case + readers + route), frontend split (date UI vs. switcher) per natural seams.
- No migration, no schema, no domain change — purely additive read-side filters and UI.

## Gate Status

### Task Completion Gate
✅ **PASS** — 23/23 tasks checked in persisted artifact; no unchecked implementation tasks remain.

### Native Review Receipt Gate
✅ **PASS** — No review was started (kill switch off); archive proceeds under ordinary repository policy.

### Verification Gate
✅ **PASS** — Verdict: PASS. 0 critical findings, 0 blockers, 7/7 requirements, 31/31 scenarios verified.

## Traceability

All artifacts retrieved from Engram (hybrid mode) with observation IDs recorded:
- Proposal (obs #428): sdd/admin-stock-movement-date-filter/proposal
- Spec (obs #429): sdd/admin-stock-movement-date-filter/spec
- Design (obs #430): sdd/admin-stock-movement-date-filter/design
- Tasks (obs #431): sdd/admin-stock-movement-date-filter/tasks
- Apply-Progress (obs #432): sdd/admin-stock-movement-date-filter/apply-progress (intermediate snapshot)
- Verify-Report (obs #434): sdd/admin-stock-movement-date-filter/verify-report
- Archive-Report (new): sdd/admin-stock-movement-date-filter/archive-report (persisted to Engram)

## Next Steps

This change is complete and ready for release. The SDD cycle is closed.
- Spec deltas synced into main specs (`openspec/specs/{domain}/spec.md`)
- Change folder archived (`openspec/changes/archive/2026-08-17-admin-stock-movement-date-filter/`)
- All artifacts persisted
- No follow-up work required unless a new change is requested
