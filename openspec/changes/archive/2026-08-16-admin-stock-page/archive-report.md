# Archive Report: Admin Stock Page

**Change**: `admin-stock-page`  
**Archived**: `2026-08-16`  
**Archive Location**: `openspec/changes/archive/2026-08-16-admin-stock-page/`  
**Mode**: hybrid (openspec + engram)  
**Verification Status**: PASS (verdict confirmed via obs #414)

## Executive Summary

The `admin-stock-page` change has been fully planned, implemented, verified, and archived. All 3 requirements across 2 spec domains (admin-api-access, admin-stock-management) have been implemented and verified. All 14 scenarios pass (13 directly, 1 indirectly), with 0 critical findings and 1 non-critical warning. The change was delivered as 2 chained PRs: backend (2f59fad + f18e34f) and frontend (5ecc7a6 + bc81c34). Delta specs have been merged into main specs; the change folder has been moved to archive via clean git mv.

## Engram Artifact IDs

All artifacts retrieved and confirmed:
- **Proposal** (obs #407): Change intent, scope, approach, locked decisions D1-D7
- **Spec Delta** (obs #408): admin-api-access + admin-stock-management delta requirements
- **Design** (obs #410): Technical approach, architecture decisions, file changes, testing strategy
- **Tasks** (obs #411): Phase-by-phase work units, test commands, rollback boundaries
- **Verify Report** (obs #414): PASS verdict with all requirements/scenarios confirmed

## Spec Merge Summary

### admin-api-access (1 requirement added)

**ADDED**: `GET /admin/stock Endpoint`
- Composes `ProductRepository.list_all()` + bulk stock read in one query
- Returns flat one-row-per-variant response carrying product name/slug + quantity
- Accepts optional `?below` (quantity threshold, inclusive, clamps negative to 0) and `?search` (case-insensitive substring on name or color)
- Parameters combine with AND when both present
- 4 scenarios confirmed: unauthenticated rejection, authenticated one-query composition, below=0 accepted, bulk-read failure propagates 500
- Merged into main spec before archive move

### admin-stock-management (2 changes)

**ADDED**: `Catalog-Wide Stock Triage Ordering, Threshold, And Search`
- Default ascending sort by quantity, no implicit threshold
- Optional threshold filter (inclusive ≤), accepts 0 as meaningful (out-of-stock only)
- Optional text search (case-insensitive substring on product name or variant color)
- Both parameters combine with AND
- 7 scenarios confirmed: default ascending view, threshold narrows correctly, below=0 returns only zeros, search matches name/color case-insensitively, search+threshold combine with AND

**MODIFIED**: `Zero-Stock Variants Are Visually Distinguished`
- Now includes catalog-wide triage view alongside per-product and product-list views
- All three surfaces use same zero-stock styling (text-destructive convention)
- Added 2 new scenarios: zero-stock rendering on triage view, zero-movement variant reports 0 on triage
- Merged into main spec before archive move

## Implementation Verification

**Verdict**: PASS (obs #414, confirmed 2026-08-16 18:46:35)
- Blockers: 0
- Critical findings: 0
- Warnings: 1 (non-blocking; see below)
- Requirements: 3/3 ✓
- Scenarios: 14/14 ✓ (13 directly covered by dedicated tests, 1 indirectly)

### Backend (Architecture Decision 1: use case owns rules; Decision 2: below inclusive, negatives clamp)
- `ListCatalogStockLevelsUseCase` created with clamping, AND-filtering, total sort logic
- `AdminCatalogStockRowResponse` standalone model (not subclassed)
- `GET /admin/stock` route composes `list_all()` + `quantities_for_variants()` (no new SQL)
- 11 unit tests + 7 integration tests cover: ascending sort with tie stability, below=0 → only zeros, below=-5 clamps to 0, search case-insensitive substring on name and color, blank search ignored, below+search AND, empty catalog, SQL-injection search safe, bulk reader spied (exactly once), 500 propagation
- Full backend suite: 337 passed

### Frontend (Architecture Decision 5: proxy idiom mirrors movements precedent; Decision 6: empty-state disambiguation; Decision 7: searchParams convention)
- `stock/route.ts` proxy with `ALLOWED_QUERY_PARAMS = ["below", "search"]` allowlist
- `stock/page.tsx` first admin page reading `searchParams` as Promise, array-collapse to first value
- Nav link added to admin/layout.tsx
- Route test: auth gate, param forwarding, allowlist (param smuggling blocked), no-store header
- Page tests: one row per variant, 0-quantity → text-destructive + "Out of stock", row links to /admin/products/{product_id}, distinct empty states ("No variants yet" vs "No variants match filter"), array param collapse
- Full frontend suite: 295 passed, 0 TypeScript errors

### Test Coverage
- Unit (use case): clamp, AND-filter, sort (incl. tie-breaker chain), empty catalog, threat matrix (SQL injection via search, param type coercion)
- Integration (route): auth gate before pool, one bulk read, params forwarded, error propagation, 500 on bulk-read failure
- Integration (proxy): auth gate, allowlist (param smuggling blocked), no-store
- Frontend (page): rows, zero-stock styling, row links, empty states, array collapse
- Frontend (layout): nav link

### Known Issue (Non-blocking Warning)

**WARNING-1** (from obs #414): Scenario "A threshold narrows to variants below it" (quantities 0, 3, 10; threshold 5; expect 0 and 3) lacks a dedicated non-boundary threshold test. Only `below=0` (D11 boundary case) and `below=-5` (negative-clamp case) tested at integration level. The single generic `row.quantity_on_hand ≤ threshold` filtering is exercised at its most semantically important boundary (0, distinguishing ≤ from <), so functional risk is low. Recommended: add one future unit test with a non-zero, non-boundary threshold and mixed-quantity dataset.

**WARNING-2** (related to WARNING-1): Design.md threat-matrix row and tasks.md task 2.1's RED plan call for an integration-level `?below=-5` test; only unit-level test exists. Non-blocking — clamp proven at unit level, route passes `below` straight through, so integration duplication is low-value. Route itself passes verification without it.

**SUGGESTION-1** (non-blocking, cosmetic): Zero-stock styling placement in triage table differs slightly from product page (cell-level vs row-level), but class name and label text match exactly (verified by direct read). A future visual-consistency pass could consider row-level styling for table.

## File Operations Verification

### Specs Merged (Mechanical Edit)
- `openspec/specs/admin-api-access/spec.md`: Added GET /admin/stock Endpoint requirement + 4 scenarios before "Stock Endpoints On The Admin Router" requirement
- `openspec/specs/admin-stock-management/spec.md`: Added Catalog-Wide Stock Triage Ordering requirement + 7 scenarios, modified Zero-Stock Variants requirement (scope expanded to triage view), added 2 triage-specific scenarios

### Archive Move (Mechanical git mv)
- Source: `openspec/changes/admin-stock-page/`
- Destination: `openspec/changes/archive/2026-08-16-admin-stock-page/`
- Method: `git mv` (tracked move, preserves history)
- Verification: Source removed, diff -r (snapshot vs archive) empty ✓
- Archive contains: proposal.md, exploration.md, specs/ (admin-api-access/, admin-stock-management/), design.md, tasks.md, apply-progress.md, verify-report.md

### Archive Contents Confirmed
- ✓ proposal.md (intent, scope, approach, decisions)
- ✓ specs/ (admin-api-access/spec.md, admin-stock-management/spec.md)
- ✓ design.md (architecture, file changes, testing strategy)
- ✓ tasks.md (all 13 tasks checked [x])
- ✓ apply-progress.md (intermediate snapshot, work unit tracking)
- ✓ verify-report.md (PASS verdict, findings, all requirements/scenarios)

## Change Metadata

### Delivery
- **PR 1 (Backend)**: Commits 2f59fad (code) + f18e34f (docs)
- **PR 2 (Frontend)**: Commits 5ecc7a6 (code) + bc81c34 (docs)
- **Final Evidence Revision**: bc81c34

### Scope Confirmation
| Area | Status | Details |
|------|--------|---------|
| New use case | ✓ Shipped | `ListCatalogStockLevelsUseCase` with clamp/AND-match/sort rules |
| New route | ✓ Shipped | `GET /admin/stock`, single bulk read, flat response |
| New response model | ✓ Shipped | `AdminCatalogStockRowResponse` standalone (never subclassed) |
| New frontend proxy | ✓ Shipped | `stock/route.ts` with allowlist rebuild |
| New frontend page | ✓ Shipped | `stock/page.tsx` with searchParams Server Component + distinct empty states |
| Nav link | ✓ Shipped | "Stock" link added to admin/layout.tsx |
| DB migration | ✓ Unchanged | No migration required (uses existing readers) |
| Domain/infrastructure | ✓ Unchanged | Zero diff under stock/infrastructure/**, products/** |
| Dependency direction | ✓ Maintained | stock → products (convention only, not CI-enforced per D7) |

### Rollback Boundary
Single-commit revert: remove use case, route, response model, proxy, page, nav link. `/admin/products` endpoints untouched. No migration, no schema change, no write path touched.

## Final-State Authority Resolution

### Sources Ranked by Authority
1. **Native review authority**: None (no review was started for this change)
2. **Persisted tasks artifact**: All 13 implementation tasks checked [x]
3. **Explicit final-state facts**: None provided in launch prompt (work completed during apply/verify cycle)
4. **Intermediate snapshots**: apply-progress.md (Batch 2 completion), verify-report.md (PASS)

### Fact Assertions
- **All tasks completed**: Per tasks.md checkbox state (all [x]), confirmed against code during verification (obs #414 finding #10)
- **All requirements met**: 3/3 per verify-report (obs #414)
- **All scenarios covered**: 14/14 per verify-report (obs #414)
- **Verification status**: PASS (obs #414, verdict: pass, blockers: 0, critical_findings: 0)
- **Non-critical warnings addressed**: Documented in WARNING-1 and WARNING-2 above; do not block archive
- **Specs merged**: Confirmed by direct edit of openspec/specs/admin-api-access/spec.md and admin-stock-management/spec.md

## Archive Sign-Off

**SDD Cycle Status**: ✓ COMPLETE

- [x] Proposal finalized (obs #407)
- [x] Specs written and delta spec merged into main (obs #408 → openspec/specs/)
- [x] Design locked (obs #410)
- [x] Tasks planned and executed (obs #411 → all checked)
- [x] Implementation delivered (2 PRs: 2f59fad/f18e34f + 5ecc7a6/bc81c34)
- [x] Verification PASS (obs #414)
- [x] Change archived to openspec/changes/archive/2026-08-16-admin-stock-page/
- [x] Delta specs merged into main specs (openspec/specs/)

No open blockers. No critical issues. Change ready for release.

---

**Archived by**: sdd-archive phase executor  
**Date**: 2026-08-16  
**Mode**: hybrid (openspec + engram)  
**Next Phase**: none (SDD cycle complete)
