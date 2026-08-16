# Archive Report: admin-initial-stock-seeding

**Archive Date**: 2026-08-16  
**Status**: Complete  
**Verdict**: PASS

## Summary

The `admin-initial-stock-seeding` change has been fully implemented, verified, and archived. This feature allows admins to set an optional initial stock quantity per variant at product creation time, seeded atomically with the product using the existing `RegisterStockedProductUseCase`.

## Change Scope

**Domains Affected**:
- `admin-product-management`: POST /admin/products now accepts optional `initial_quantity` per variant
- `stock-movement-recording`: Atomic product creation with initial stock movements exposed

**Key Requirements Delivered**: 2/2 domains  
**Spec Scenarios Passing**: 9/9

## Artifacts Persisted

All SDD artifacts were successfully persisted to both Engram and OpenSpec:

| Artifact | Engram ID | Type | Status |
|----------|-----------|------|--------|
| Proposal | #387 | architecture | Confirmed |
| Spec Deltas | #388 | architecture | Confirmed (merged into main specs) |
| Design | #389 | architecture | Confirmed |
| Tasks | #390 | architecture | Confirmed (all 14/14 complete) |
| Verify Report | #393 | architecture | PASS (verdict: pass, blockers: 0, critical: 0) |

## Implementation Status

**Tasks Completed**: 14/14 (100%)

- Phase 1 Backend (2 tasks): CreateStockedProductUseCase implemented
- Phase 2 Route Wiring (4 tasks): Route refactored to use transaction(pool); _FakePool patched
- Phase 3 Frontend (4 tasks): Create-only initial-quantity field rendered and wired
- Phase 4 Verification (4 tasks): Full test suite passes (306 backend + 278 frontend)

All tasks marked complete in persisted `tasks.md`.

## Specification Merge

**Main Specs Updated**:
1. `openspec/specs/admin-product-management/spec.md` — Added new requirement "Product Creation Accepts An Optional Initial Quantity Per Variant" with 5 scenarios
2. `openspec/specs/stock-movement-recording/spec.md` — Added new requirement "Atomic Registration Of A New Product With Initial Stock Movements" with 4 scenarios

**Merge Method**: Delta requirements appended to main specs; all prior requirements preserved.

## Verification Results

**Build**: PASS  
**Tests**: PASS
- Backend: 306/306 (112 focused on this change)
- Frontend: 278/278 (53 focused on this change)
- Domain boundary tests: PASS

**Coverage**: 9/9 specification scenarios compliant with dedicated test coverage:
- Positive initial quantity seeds exactly one restock movement (atomic)
- Zero/absent initial quantity records no movement
- Negative initial quantity rejected with 422 before any write
- Seed movement failure rolls back entire creation (product + all variants)
- PATCH endpoint silently accepts but ignores the field
- Mixed variants seed only positive-quantity ones
- Mid-composition failure produces zero partial state
- Non-zero movement invariant never bypassed

**Issues**: None (CRITICAL: 0, WARNING: 0, SUGGESTION: 0 in verify-report)

## Design Decisions Honored

| Decision | Status | Verification |
|----------|--------|--------------|
| D1: New `CreateStockedProductUseCase` in `stock/application/` | Honored | File `create_stocked_product.py` created, mirrors `CreateProductUseCase`, delegates to `RegisterStockedProductUseCase` |
| D2: Seed-quantity → movement rule in use case | Honored | `execute()` filters `initial_quantities > 0` before construction; route supplies keyed mapping |
| D3: `_FakePool.transaction()` added to both class definitions | Honored | Both definitions at lines 41 and 153 patched; regression tests pass |
| D4: Field render gated on `row.id === null && productId === undefined` | Honored | `product-form.tsx` line 253 implements exact rule; 3 dedicated tests confirm correct gating |

## Proposal Locked Decisions

Both locked decisions from the proposal Question Round were honored:
- **D1 (POST-only v1)**: Confirmed — `PATCH /admin/products/{id}` never reads `initial_quantity`
- **D2 (Shared model)**: Confirmed — One `AdminVariantInput` model, route-level behavior differs

## Rollback Plan

Single-commit revert via `git revert`. No schema changes, no migration, no data backfill. Existing seed movements remain valid `restock` rows in the append-only ledger. Route reverts to `CreateProductUseCase` with no residual state.

## Archive Location

- **Filesystem**: `openspec/changes/archive/2026-08-16-admin-initial-stock-seeding/`
- **Contents**:
  - proposal.md (user intent, locked decisions)
  - design.md (architecture, 4 decisions, file changes)
  - exploration.md (context and research)
  - tasks.md (14 implementation tasks, all complete)
  - verify-report.md (PASS verdict, all tests)
  - specs/ (delta specs for both domains)
  - apply-progress.md (implementation audit trail)

## Source of Truth Updated

The main OpenSpec files now reflect the shipped behavior:
- `openspec/specs/admin-product-management/spec.md` — New capability: optional initial-quantity on product creation
- `openspec/specs/stock-movement-recording/spec.md` — New capability: atomic product + initial-movements composition

## SDD Cycle Complete

The change has been fully planned (proposal), specified (specs), designed (architecture decisions), implemented (tasks), verified (tests), and archived. Ready for next change.

---

**Archived by**: sdd-archive executor  
**Mode**: hybrid (Engram + OpenSpec)  
**Observation IDs for Traceability**:
- Proposal: #387
- Spec: #388
- Design: #389
- Tasks: #390
- Verify Report: #393
