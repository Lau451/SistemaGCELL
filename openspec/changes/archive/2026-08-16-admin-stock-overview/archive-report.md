# Archive Report: Admin Stock Overview

**Change**: admin-stock-overview  
**Archived**: 2026-08-16  
**Status**: Complete  
**Verification Verdict**: PASS (0 blockers, 0 critical findings)

## Summary

The `admin-stock-overview` SDD change has been fully planned, implemented, verified, and archived. Admins can now view per-variant stock quantities directly in the product list (`GET /admin/products`), eliminating the need to open each product detail page individually to answer "what is running low?"

All tasks completed (13/13 ✓). All requirements verified (4/4). All scenarios validated (7/7).

## Artifact Lineage

Prior phase artifacts (Engram, hybrid mode):

| Artifact | ID | Timestamp | Type |
|----------|----|-----------|----|
| sdd/admin-stock-overview/proposal | #397 | 2026-08-16 11:55:58 | architecture |
| sdd/admin-stock-overview/spec | #398 | 2026-08-16 12:17:25 | architecture |
| sdd/admin-stock-overview/design | #399 | 2026-08-16 12:19:27 | architecture |
| sdd/admin-stock-overview/tasks | #400 | 2026-08-16 12:26:01 | architecture |
| sdd/admin-stock-overview/verify-report | #402 | 2026-08-16 12:36:56 | architecture |

All observations are archived in Engram for audit trail and future reference.

## Specifications Merged

Delta specs from `openspec/changes/admin-stock-overview/specs/` have been merged into main specs under `openspec/specs/`. All three domains received additions or modifications:

### Domain: admin-stock-management

**Action**: Added + Modified  
**Details**:
- **ADDED**: Requirement "Bulk Catalog-Wide Current-Stock Read" (2 scenarios)
  - Bulk read returning `dict[UUID, int]` for all variants in one aggregate query
  - Variant with zero movements → 0 (never missing key)
  - One query regardless of variant count
  
- **MODIFIED**: Requirement "Zero-Stock Variants Are Visually Distinguished"
  - Extended scope: now applies to BOTH per-product detail view AND admin product list
  - Added scenario: "A zero-stock variant renders with distinct styling on the admin product list"
  - Maintains consistency across both surfaces

### Domain: admin-api-access

**Action**: Added  
**Details**:
- **ADDED**: Requirement "GET /admin/products Response Includes Per-Variant Current Stock" (2 scenarios)
  - Composes `ProductRepository.list_all()` with exactly one bulk stock read
  - Stock is part of response contract — bulk read failure fails whole request
  - Never returns partial/degraded list with missing or null stock

### Domain: admin-product-management

**Action**: Added  
**Details**:
- **ADDED**: Requirement "Admin Product List Displays Per-Variant Current Stock" (1 scenario)
  - Renders per-variant stock sourced entirely from `GET /admin/products` response
  - No additional per-product or per-variant stock requests
  - Leverages composed bulk read from admin-api-access

## Implementation State (Final)

**Tasks**: 13/13 complete (all checkboxes ✓)

Per verify-report (obs #402):
- All implementation tasks verified against actual codebase
- Backend test suite: 319 passed
- Frontend test suite: 281 passed (42 files)
- No Supabase migration/schema/domain changes
- CatalogStockLevelsReader Protocol is genuine sibling (StockLevelReader untouched)
- Both adapters (Postgres + In-memory) implement seed-then-overlay totality
- AdminProductListItemResponse/AdminProductListVariantResponse are separate models
- list_admin_products calls quantities_for_variants exactly once (single query)
- Bulk read failure returns 500 with no partial body (no _execute_or_raise wrapping)
- Zero-stock styling reuses exact text-destructive class and "Out of stock" label from stock-manager.tsx

**Task Completion Gate**: PASS
- All 13 implementation tasks marked complete in `tasks.md`
- apply-progress.md claims match actual code state (319 backend, 281 frontend tests)
- No stale unchecked tasks

## Verification Results

**Verdict**: PASS  
**Blockers**: 0  
**Critical Findings**: 0  
**Warnings**: 0  
**Suggestions**: 1 (non-blocking)

**Requirements Coverage**: 4/4 (100%)
- Bulk Catalog-Wide Current-Stock Read ✓
- Zero-Stock Variants Are Visually Distinguished (extended) ✓
- GET /admin/products Response Includes Per-Variant Current Stock ✓
- Admin Product List Displays Per-Variant Current Stock ✓

**Scenarios Coverage**: 7/7 (100%)
- Bulk read returns quantity for every variant across catalog in one query ✓
- Variant with zero movements resolves to 0 (not missing key) ✓
- Response includes per-variant stock for every returned product ✓
- Bulk stock read failure fails whole request ✓
- Admin list displays each variant's current stock quantity ✓
- Zero-stock variant renders with distinct styling on detail view ✓
- Zero-stock variant renders with distinct styling on admin product list ✓

**Suggestion** (non-blocking, per obs #402):
> The 500-failure test only asserts status_code == 500, not that the body carries no partial/degraded product data. Acceptable since FastAPI's unhandled-exception path returns no product JSON body at all, but an explicit body-shape assertion would make the "no partial body" spec wording airtight.

## Archive Folder Structure

```
openspec/changes/archive/2026-08-16-admin-stock-overview/
├── proposal.md
├── design.md
├── tasks.md (all 13 tasks: ✓)
├── specs/
│   ├── admin-stock-management/spec.md
│   ├── admin-api-access/spec.md
│   └── admin-product-management/spec.md
└── archive-report.md (this file)
```

## Rollback Boundary

Single-commit revert, clean via `git revert`:
- No migration, no schema change, no data written to database
- Read-only end-to-end; write paths (stock movements, product CRUD) untouched
- `supabase/migrations/` unchanged
- `backend/src/gcell/stock/domain/` unchanged
- Revert would restore prior response contract by removing `quantity_on_hand` from admin list variants

## Locked Decisions (User-Confirmed)

Per proposal (obs #397):

| # | Decision | Status |
|---|----------|--------|
| D1 | Per-variant quantities only (no summed per-product totals) | Implemented ✓ |
| D2 | Stock added to EXISTING GET /admin/products response (no new endpoint) | Implemented ✓ |
| D3 | Single bulk aggregate query (no per-variant loop) | Verified in tests ✓ |
| D4 | Legal dependency direction `stock → products` unchanged | Verified (domain_boundary tests pass) ✓ |

## SDD Cycle Closure

This archive marks the formal end of the SDD cycle for `admin-stock-overview`. The change is:

- ✓ Fully specified (proposal, specs, design, tasks)
- ✓ Fully implemented (all tasks complete, all tests passing)
- ✓ Fully verified (4/4 requirements, 7/7 scenarios, 0 blockers)
- ✓ Fully archived (specs merged, folder moved, artifacts recorded)

No follow-up work required. Ready for the next SDD change.

---

**Archive Report Created**: 2026-08-16  
**Persisted to**: Engram (topic: `sdd/admin-stock-overview/archive-report`)  
**Repository State**: Specs merged in openspec/ (uncommitted), folder archived via git mv (staged)
