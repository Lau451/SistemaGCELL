# Archive Report: CI and RLS Tests

**Change**: `ci-and-rls-tests`  
**Status**: ARCHIVED  
**Date Archived**: 2026-08-17  
**Verification**: PASS WITH WARNINGS (commit `38c833b`, D5 documentation-only issue corrected pre-archive)  
**HEAD at archive time**: `199457c783756e4a086ccb1eb769daadd1ceeba7` (per verify-report evidence_revision)

## Executive Summary

The `ci-and-rls-tests` change has been successfully planned, implemented, verified, and archived. This change delivered the repository's first-ever CI pipeline (GitHub Actions workflow with parallel backend/frontend jobs and ephemeral Postgres service) plus the first-ever RLS integration test module (64 dedicated row-level security tests exercising SQL-level role enforcement). Delivered as 4 chained PRs, each independently verified green on live GitHub Actions; 28/28 tasks complete; full verification suite passing (422 backend tests including 64 RLS tests, 344 frontend tests, 6 CI safety tests, zero type errors, zero critical issues).

## Change Intent

Establish automated quality gates (CI) that execute the repo's existing pinned test/lint/build commands on every push and pull request, and create a dedicated RLS integration test module that exercises the row-level security policies already defined in `product-catalog-schema`, `inventory-schema`, and `product-media-storage` specs. Enable developers to verify security constraints before merge without manual pre-flight testing.

## Specs Merged

| Domain | Action | Details |
|--------|--------|---------|
| platform-foundation | ADDED | One new requirement: "Automated CI Pipeline Enforces Pinned Quality Gates And RLS Tests" (3 scenarios covering pinned commands execution, live database backend tests, and RLS integration test module wiring) |

**Merge method**: Delta spec appended to existing main spec. Existing 9 requirements (Frontend Scaffold, Backend Scaffold, Hexagonal Boundary, Supabase CLI, Testing Config, PWA Strategy, Fresh Clone, DB Pool Lifecycle, Backend Boot Lifespan) preserved verbatim.

## Deliverables

### Files Created/Modified

**CI Workflow**:
- `.github/workflows/ci.yml` — GitHub Actions workflow with 2 parallel jobs (backend: ruff check + pytest + bootstrap + replay; frontend: npm lint + npm test + npm build)
- `.github/workflows/README.md` — documenting trigger events, job structure, environment vars

**RLS Integration Tests**:
- `backend/tests/integration/db/test_rls_policies.py` — 64 tests (Part A: 53 role-boundary tests; Part B: 11 append-only trigger tests) exercising role-level access control via `SET ROLE`, soft-delete behavior, privilege matrices, storage policies
- `backend/tests/architecture/test_ci_workflow_safety.py` — 6 safety regression tests confirming no real secrets embedded, no forbidden imports, correct role scoping

**CI Bootstrap & Replay SQL**:
- `supabase/ci/00_supabase_roles.sql` — role creation for CI
- `supabase/ci/01_storage_schema.sql` — ephemeral bucket provisioning for test

**Config & Docs**:
- `openspec/config.yaml` — populated `testing:` block with backend and frontend commands
- Various test environment updates

### Commits Delivered
Four chained PRs (abbreviated):
1. **PR1**: CI workflow skeleton + bootstrap SQL + RLS test module Part A
2. **PR2**: RLS test module Part B + append-only trigger tests
3. **PR3**: Frontend test fixes (timezone mock, CRLF normalization) + CI safety tests
4. **PR4**: Final regression + apply-progress closure

### Task Completion
**28/28 tasks complete** across 5 phases (Phase 0: planning; Phases 1-4: batched work; Phase 5: regression). All marked `[x]` with Result notes. Independently verified against actual code/config.

## Verification Results

**Verdict**: PASS WITH WARNINGS  
**Observation**: obs #445 (verify-report), created 2026-08-17 12:01:02

### Issues Summary
- **CRITICAL**: 0
- **WARNING**: 1 (D5 self-verification used wrong git baseline in task 5.3; documentation-only audit-trail accuracy issue, no code impact; corrected in commit 38c833b before this archive)
- **SUGGESTION**: 1 (apply-progress.md missing Phase 5 formal section; content exists in tasks.md)

### Test Execution (independently reproduced this session)
| Test Suite | Result |
|---|---|
| Backend pytest | 422 passed, 2 warnings |
| RLS policies | 64 passed (53 Part A + 11 Part B) |
| CI safety tests | 6 passed |
| Frontend Vitest | 344 passed across 47 files |
| Ruff check | All passed |
| Ruff format check | Non-zero exit (44 files would reformat) — correctly omitted from CI per DD2a |

### Specification Compliance
All 3 scenarios in the new CI requirement verified:
1. **CI runs both stacks' pinned commands**: ✅ Live GitHub Actions runs 31992452282, 32038510858, 32040002913 confirmed execution of `ruff check`, `pytest -q`, `npm run lint`, `npm test -- --run`, `npm run build`
2. **Backend tests run against live database**: ✅ Ephemeral `postgres:17` service with `supabase/migrations/` replayed; 422 tests executed (not skipped); matches live CI and local reproductions
3. **RLS requirements exercised by dedicated tests**: ✅ `test_rls_policies.py` covers anon/authenticated denial, privilege matrices, soft-delete on public views, grant-layer vs. trigger-layer append-only enforcement, storage policies

### Design Decisions (DD1-DD5) Compliance
| Decision | Status | Notes |
|---|---|---|
| DD1: Vanilla postgres:17 + CI-only bootstrap SQL | ✅ PASS | Uses literal placeholders (loopback IPs, ci-placeholder-anon-key) |
| DD2a: ruff format --check precondition, omit from CI | ✅ PASS | Correctly absent from ci.yml; exit non-zero (44 files) confirms necessity |
| DD2b: next build as type gate; no tsc script | ✅ PASS | openspec/config.yaml reconciled; `npm run build` is the gate |
| DD3: push→main, PR→main, dispatch; 2 parallel jobs | ✅ PASS | ci.yml structure matches exactly |
| DD4: RLS tests reuse db_conn, SAVEPOINT-scoped as_role() | ✅ PASS | No conftest.py changes; as_role() matches spec |
| DD5: Grant-layer vs. trigger-layer append-only separation | ✅ PASS | Different test functions, roles, exception types — genuinely separate |

**Note on D5 WARNING**: Task 5.3 self-verification used commit `6b92241` (mid-change) as baseline instead of true pre-change baseline `8ff7b7c`. This revealed 2 test-file changes in frontend/src (15 lines, zero production code). The substantive D5 intent (no production code changes) holds true; documentation audit-trail wording in design.md and apply-progress.md was inaccurate. Corrected by user before this archive in commit 38c833b.

## Archive Contents

Archived to: `openspec/changes/archive/2026-08-17-ci-and-rls-tests/`

- proposal.md — scope, approach, timeline, rollback plan
- design.md — technical approach, DD1-DD5 decisions, file structure, testing strategy, security model
- specs/platform-foundation/spec.md — delta spec (1 ADDED requirement with 3 scenarios)
- tasks.md — 28 phased work units across 5 phases, TDD-paired, all complete
- apply-progress.md — cumulative evidence across 4 batches (PRs 1-4)
- verify-report.md — full verification with compliance matrices (PASS WITH WARNINGS, D5 documentation issue corrected pre-archive)
- archive-report.md — this document

**Diff verification**: Source snapshot vs. archived folder, empty diff (byte-identical). Clean rename via `git mv`.

## Gate Status

- **Task Completion Gate**: ✅ PASS (28/28 checked, 0 unchecked)
- **Native Review Receipt Gate**: ✅ PASS (no review started for this candidate)
- **Verification Gate**: ✅ PASS (verdict PASS WITH WARNINGS, 0 CRITICAL issues, D5 documentation-only issue corrected pre-archive per commit 38c833b)

## Traceability

Artifacts retrieved from Engram (hybrid mode):
- Proposal: obs #438
- Spec: obs #439
- Design: obs #440
- Tasks: obs #442
- Apply-Progress: obs #443
- Verify-Report: obs #445
- Archive-Report: obs TBD (persisted to Engram)

All observation IDs recorded for traceability and future reference.

## Result

Change fully archived and merged into main specs. SDD cycle complete. Ready for release and baseline for future changes.

---

**Archive Execution Summary**:
- Specs merged: openspec/specs/platform-foundation/spec.md updated with 1 ADDED requirement
- Change folder moved: `openspec/changes/ci-and-rls-tests/` → `openspec/changes/archive/2026-08-17-ci-and-rls-tests/`
- Archive verification: byte-identical (empty diff)
- Mode: hybrid (filesystem + Engram)
- Session: archive executor (sdd-archive phase)
