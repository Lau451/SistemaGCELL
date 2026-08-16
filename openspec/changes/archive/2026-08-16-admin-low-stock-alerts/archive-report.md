# Archive Report: Admin Low-Stock Alerts

**Change**: `admin-low-stock-alerts`  
**Archived**: `2026-08-16`  
**Archive Location**: `openspec/changes/archive/2026-08-16-admin-low-stock-alerts/`  
**Mode**: hybrid (openspec + engram)  
**Verification Status**: PASS (verdict confirmed via obs #424)

## Executive Summary

The `admin-low-stock-alerts` change has been fully planned, implemented, verified, and archived. All 2 requirements across 1 spec domain (admin-stock-management) have been implemented and verified. All 6 scenarios pass, with 0 critical findings and 0 warnings. The change was delivered as a single frontend-only PR (commit 91aabed), comprising 2 new async Server Component files + 2 modified layout/test files, with zero backend or migration changes. Delta specs have been merged into main specs; the change folder has been moved to archive via clean git mv.

## Engram Artifact IDs

All artifacts retrieved and confirmed:
- **Proposal** (obs #419): Change intent, scope, approach, locked decisions D1-D4, open questions OQ1-OQ4
- **Spec Delta** (obs #420): admin-stock-management delta — 2 new requirements (Badge Count, Badge Presentation)
- **Design** (obs #421): Technical approach, architecture decisions D1-D7, file changes, testing strategy, threat matrix
- **Tasks** (obs #422): Phase-by-phase work units (5 phases, 20 total tasks), test commands, rollback boundary
- **Verify Report** (obs #424): PASS verdict with all requirements/scenarios confirmed, 45/45 frontend test files passed, zero type errors

## Spec Merge Summary

### admin-stock-management (2 requirements added)

**ADDED**: `Admin Nav Low-Stock Badge Count`
- Computes low-stock count on every `/admin/*` page load, attached to "Stock" nav link
- Count equals number of variants with `quantity <= 5` (fixed, inclusive threshold)
- Calls existing `GET /admin/stock?below=5` route unchanged, reuses `ListCatalogStockLevelsUseCase` and `CatalogStockLevelsReader.quantities_for_variants()` bulk read
- No new query path, no per-variant query, no new backend route or port
- Badge default independent of triage view default (no implicit threshold)
- 3 scenarios confirmed: threshold reflects count at exactly 5, count reuses existing bulk read, count reflects whole catalog

**ADDED**: `Admin Nav Low-Stock Badge Presentation`
- Badge renders only as addition to existing "Stock" nav link
- At count 0, badge hidden entirely (no `Stock (0)` state)
- At non-zero count, renders exact count with `text-destructive` styling (existing convention)
- Activating badge navigates to `/admin/stock`
- 3 scenarios confirmed: zero count hides badge, non-zero renders with destructive styling, badge click navigates to triage page

**Merged into main spec before archive move**

## Implementation Verification

**Verdict**: PASS (obs #424, confirmed 2026-08-16 20:13:53)
- Blockers: 0
- Critical findings: 0
- Warnings: 0
- Suggestions: 0
- Requirements: 2/2 ✓
- Scenarios: 6/6 ✓
- Tasks: 20/20 ✓

### Frontend (Architecture Decisions 1-7)
- **Decision 1**: Isolated async `StockAlertBadge` RSC mounted via `<Suspense fallback={null}>`, `AdminLayout` stays sync
- **Decision 2**: Fetch failure, non-ok, malformed body, AND zero all collapse to `null`, never throws
- **File Changes**:
  - Created: `frontend/src/app/(admin)/admin/stock-alert-badge.tsx` (async RSC, ~50 lines)
  - Created: `frontend/src/app/(admin)/admin/stock-alert-badge.test.tsx` (~45 lines)
  - Modified: `frontend/src/app/(admin)/admin/layout.tsx` (added Suspense wrapper + badge component)
  - Modified: `frontend/src/app/(admin)/admin/layout.test.tsx` (added 1 test case, mocking badge)
- **Test Coverage**:
  - Unit (badge): fetch URL exact, cookie forwarding, count > 0 renders with text-destructive, count = 0 returns null, fetch throw → null, non-ok response → null, malformed body → null
  - Unit (layout): badge mocked as sync stub, renders inside Stock link, accessible name preserved
  - Full suite: 45/45 files passed, 302/302 tests passed (one pre-existing flake in image-manager.test.tsx, unrelated, confirmed flaky)
  - Type check: clean, zero output, zero type errors
  - Focused: 2/2 files, 11/11 tests passed for stock-alert-badge and layout

### Zero Backend/Migration Changes
- `git diff --stat` shows exactly 4 files changed, all under `frontend/src/app/(admin)/admin/`
- Scoped diff against `backend/`, `supabase/migrations/`, and `frontend/src/app/api/admin/stock/route.ts` returned empty
- Zero backend files, zero proxy changes, zero migration (matching proposal.md Affected Areas — all listed "Unchanged")

### Evidence Revision
- Final evidence revision: 91aabed (verified by verify-report.md)

## File Operations Verification

### Specs Merged (Mechanical Edit)
- `openspec/specs/admin-stock-management/spec.md`: Added 2 requirements (Admin Nav Low-Stock Badge Count + Badge Presentation) with 3 + 3 scenarios each, after existing Movement History Ownership requirement, preserving all prior requirements intact

### Archive Move (Mechanical git mv)
- Source: `openspec/changes/admin-low-stock-alerts/`
- Destination: `openspec/changes/archive/2026-08-16-admin-low-stock-alerts/`
- Method: `git mv` (tracked move, preserves history)
- Source removed: Confirmed (ls error: No such file or directory)
- Archive contains: proposal.md, exploration.md, specs/admin-stock-management/spec.md, design.md, tasks.md, apply-progress.md, verify-report.md

### Archive Contents Confirmed
- ✓ proposal.md (intent, scope, approach, decisions D1-D4, open questions OQ1-OQ4)
- ✓ exploration.md (research and discovery)
- ✓ specs/admin-stock-management/spec.md (delta — 2 added requirements, 6 scenarios)
- ✓ design.md (architecture, file changes, testing strategy, threat matrix, migration/rollout)
- ✓ tasks.md (all 20 tasks checked [x], 5 phases: RED/GREEN badge component, RED/GREEN layout wiring, verification)
- ✓ apply-progress.md (intermediate snapshot, work unit tracking)
- ✓ verify-report.md (PASS verdict, findings, all requirements/scenarios, test evidence)

## Change Metadata

### Delivery
- **PR**: Single (commit 91aabed, per verify-report evidence_revision)
- **Scope**: Frontend-only, read-only, no backend/infrastructure changes
- **Lines Changed**: ~180–230 per estimate (2 new files ~90 lines, 2 modified files ~15 + ~40 lines) — actual: 4 files, low risk
- **Review Budget**: Low (under 400-line threshold)

### Scope Confirmation
| Area | Status | Details |
|------|--------|---------|
| New Server Component | ✓ Shipped | `StockAlertBadge` async RSC with safe fetch + null fallback |
| New test file | ✓ Shipped | `stock-alert-badge.test.tsx` with 6 test cases (threshold, zero, 3 failure modes) |
| Modified layout | ✓ Shipped | `layout.tsx` Suspense + badge integration |
| Modified layout test | ✓ Shipped | `layout.test.tsx` 1 new test + 4 existing cases all passing |
| Backend route | ✓ Unchanged | `GET /admin/stock?below=5` reused as-is |
| Backend use case | ✓ Unchanged | `ListCatalogStockLevelsUseCase` reused as-is |
| Backend reader | ✓ Unchanged | `CatalogStockLevelsReader.quantities_for_variants()` reused as-is |
| Proxy | ✓ Unchanged | No allowlist rebuild required (existing `?below` param already forwarded) |
| DB migration | ✓ Unchanged | No migration required (read-only, no schema changes) |
| Domain | ✓ Unchanged | Zero diff under backend/src/gcell/**, stock/**, products/** |
| Admin landing page | ✓ Unchanged | `/admin/page.tsx` has zero new imports/widgets |

### Rollback Boundary
Single-commit revert: remove `StockAlertBadge` component, remove badge test file, remove `Suspense` wrapper + component import from `layout.tsx`, remove new test case from `layout.test.tsx`. `/admin/*` shell unaffected except for badge removal (Link and layout behavior unchanged). No migration, no schema change, no write path touched.

## Final-State Authority Resolution

### Sources Ranked by Authority
1. **Native review authority**: None (no review was started for this change; kill switch off)
2. **Persisted tasks artifact**: All 20 implementation tasks checked [x] in tasks.md
3. **Explicit final-state facts**: None provided in launch prompt (work completed during apply/verify cycle)
4. **Intermediate snapshots**: apply-progress.md (completion status), verify-report.md (PASS)

### Fact Assertions
- **All tasks completed**: Per tasks.md checkbox state (all [x], matching apply-progress.md's reported 20/20)
- **All requirements met**: 2/2 per verify-report (obs #424)
- **All scenarios covered**: 6/6 per verify-report (obs #424, all covered by passing runtime tests)
- **Verification status**: PASS (obs #424, verdict: pass, blockers: 0, critical_findings: 0, warnings: 0)
- **No critical issues**: Zero critical findings per verify-report; archive not blocked
- **Specs merged**: Confirmed by direct edit of openspec/specs/admin-stock-management/spec.md, existing "Default view is ascending by quantity with no implicit filtering" requirement untouched

## Archive Sign-Off

**SDD Cycle Status**: ✓ COMPLETE

- [x] Proposal finalized (obs #419)
- [x] Specs written and delta spec merged into main (obs #420 → openspec/specs/admin-stock-management/spec.md)
- [x] Design locked (obs #421)
- [x] Tasks planned and executed (obs #422 → all 20 checked)
- [x] Implementation delivered (single commit 91aabed, frontend-only)
- [x] Verification PASS (obs #424, 2/2 requirements, 6/6 scenarios, 20/20 tasks)
- [x] Change archived to openspec/changes/archive/2026-08-16-admin-low-stock-alerts/
- [x] Delta specs merged into main specs (openspec/specs/admin-stock-management/spec.md)

No open blockers. No critical issues. Change ready for release.

---

**Archived by**: sdd-archive phase executor  
**Date**: 2026-08-16  
**Mode**: hybrid (openspec + engram)  
**Next Phase**: none (SDD cycle complete)
