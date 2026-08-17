# Verification Report: ci-and-rls-tests

**Verdict: PASS WITH WARNINGS**
**evidence_revision (HEAD)**: `199457c783756e4a086ccb1eb769daadd1ceeba7`
**True pre-change baseline** (verified via `git log`, NOT the `6b92241` apply-progress used): `8ff7b7c` (docs(sdd): archive admin-stock-movement-date-filter) — this is the parent of `2080432`, the first commit of this change.

## Task Completeness

28/28 tasks in tasks.md marked [x] across Phases 0-5, each with a Result note. Independently spot-checked against actual code/config — all match.

## Independent Test Execution (this session, live local Supabase Postgres at 127.0.0.1:54322)

| Command | Result | Matches claim? |
|---|---|---|
| `cd backend && DB_URL=... uv run pytest -q` | **422 passed**, 2 warnings | Yes (apply-progress + PR3+PR4 CI run 32040002913 both say 422) |
| `uv run pytest backend/tests/integration/db/test_rls_policies.py -q` | **64 passed** | Yes (53 Part A + 11 Part B) |
| `uv run pytest backend/tests/architecture/test_ci_workflow_safety.py -v` | **6 passed** | Yes |
| `uv run ruff check` | All checks passed | Yes |
| `uv run ruff format --check` | non-zero (44 files would reformat) | Confirms DD2a's step-omission is still correctly justified today |
| `cd frontend && npm test -- --run` | **344 passed**, 47 files | Yes |
| Direct `docker exec ... psql` row counts on products/stock_movements/storage.buckets/storage.objects | all 0 | Confirms zero test-data leakage independently, not just trusting the report |

## D1-D7 Compliance Matrix

| Decision | Status | Evidence |
|---|---|---|
| D1 (one bundled change, no admin- prefix) | PASS | `openspec/changes/ci-and-rls-tests/` |
| D2 (zero real secrets) | PASS | `grep -iE '\$\{\{ secrets\.\|sk-...\|supabase\.co'` across the FULL correct-baseline diff (`8ff7b7c..HEAD`) → every match is inside the safety-test's own assertion text or docs describing what NOT to do, never an actual secret. `ci.yml` uses only literal loopback placeholders (`http://127.0.0.1:54321`, `ci-placeholder-anon-key`) and zero `${{ secrets. }}` tokens |
| D3 (RLS scope SQL-level only, SET ROLE via db_conn) | PASS | `test_rls_policies.py` uses `db_conn` + `as_role()` (`SET LOCAL ROLE` inside a SAVEPOINT); no PostgREST/HTTP test present |
| D4 (CI actually runs the new RLS tests) | PASS | `ci.yml`'s backend job runs bare `uv run pytest -q` from `working-directory: backend` with no path filter; `pyproject.toml` has `testpaths = ["tests"]` (no exclusion), so `test_rls_policies.py` is unconditionally collected. Live GitHub Actions run 32040002913: `422 passed` — exactly matches the local run reproduced this session, which includes all 64 RLS tests. Wiring confirmed, not just file existence |
| D5 (zero diff in backend/src, frontend/src, supabase/migrations) | **WARNING — see below** | `backend/src` and `supabase/migrations`: genuinely zero diff across the correct baseline. `frontend/src`: NOT zero — 2 files modified (15 lines) |
| D6 (wire existing commands only, no new gates beyond DD2) | PASS | `ci.yml` runs exactly: `ruff check`, `pytest -q`, `npm run lint`, `npm test -- --run`, `npm run build`; no `ruff format --check` step present (correctly omitted per DD2a) |
| D7 (red CI is advisory only, no branch-protection enforcement in this diff) | PASS (diff-verifiable part only) | Nothing in the diff touches branch-protection/required-status-check settings. Actual GitHub repo *settings* enforcement is outside git and outside this session's verification capability (would need GH API/admin access) |

### WARNING — D5 self-verification used the wrong git baseline

Task 5.3 in tasks.md ran `git diff 6b92241..HEAD --stat -- supabase/migrations backend/src frontend/src` and reported "empty (D5 confirmed across the whole change)". **`6b92241` is NOT the pre-change baseline — it is a commit already inside this SDD change** (the 4th commit of the change, "confirm PR1 CI skeleton green"), landing *after* `84f3eab` (first CI workflow) and `8b0cf22` ("fix: latent test issues surfaced by running CI for the first time").

Using the true baseline (`8ff7b7c`, verified via `git log 8ff7b7c..199457c --oneline`), the actual diff is:

```
frontend/src/app/(admin)/admin/products/stock-history.test.tsx        | 1 +
frontend/src/lib/pwa/__tests__/catalog-route-conformance.test.ts      | 14 +++++++++++--
```

Both are pre-existing **test files** modified to fix environment-dependent flakiness first surfaced by running CI for the first time (a `getTimezoneOffset` mock, and CRLF→LF hash-pin normalization) — confirmed by reading the actual diff content. Zero application/domain/API code was touched; the substantive intent of D5 (no production code changes) genuinely holds. But:

1. `design.md`'s File Changes table explicitly lists `frontend/src/**` as "**Unchanged**" — this is factually false.
2. `apply-progress.md`'s Batch-1/PR1 section states "test-file-only changes, zero `backend/src`/`frontend/src` touched" — also factually false (they ARE physically under `frontend/src/`, just as test files, per this repo's Next.js/Vitest co-location convention).
3. Task 5.3's own closing claim "D5 confirmed across the whole change" is not actually true for the whole change — it excluded 2 of the 15 files in the real diff by using a mid-change commit as the baseline.

**Recommendation**: correct design.md's File Changes table and apply-progress's PR1 section wording before archive (documentation-only fix, no code change needed), since the underlying guarantee (no production code touched) is real — only the written audit trail is inaccurate.

## DD1-DD5 Compliance Matrix

| Decision | Status | Evidence |
|---|---|---|
| DD1 (vanilla postgres:17 + CI-only bootstrap SQL) | PASS | `supabase/ci/00_supabase_roles.sql` and `01_storage_schema.sql` read verbatim, match design.md's Interfaces/Contracts exactly |
| DD2a (ruff format --check apply-time precondition) | PASS | Exit non-zero at apply time (recorded); step correctly absent from `ci.yml`; re-verified non-zero today (44 files) |
| DD2b (no standalone tsc, next build is type gate; config.yaml reconciled) | PASS | `openspec/config.yaml` diff matches literal DD2b string exactly; no typecheck script added to `frontend/package.json` |
| DD3 (push→main + PR→main + workflow_dispatch, 2 parallel jobs, `if: !cancelled()` on gate steps only) | PASS | `ci.yml` matches exactly: triggers, concurrency group, no `needs:`, `if: ${{ !cancelled() }}` present on eslint/vitest/build/ruff-check/pytest steps but NOT on checkout/setup/install/bootstrap/replay steps |
| DD4 (RLS tests reuse db_conn unchanged, module-local as_role() SAVEPOINT) | PASS | No conftest.py change in diff; `as_role()` implemented exactly as design.md specifies |
| DD5 (two genuinely separate append-only assertions: grant-layer via service_role, trigger-layer via owner/superuser) | **PASS — confirmed genuinely separate** | `test_service_role_update_denied_on_stock_movements`/`..._delete_denied...` run under `as_role(db_conn, "service_role")`, assert `InsufficientPrivilegeError` (grant layer, never reaches the trigger). `test_owner_update_denied_by_append_only_trigger_on_stock_movements`/`..._delete_denied...` run on `db_conn` **directly** (the owner/superuser connection, no role switch at all), assert `asyncpg.exceptions.RaiseError` matching `"append-only"` (trigger layer). Different connections/roles, different exception types, different test functions — not conflated |

## Spec Compliance Matrix (openspec/changes/ci-and-rls-tests/specs/platform-foundation/spec.md)

| Scenario | Status | Covering evidence |
|---|---|---|
| CI runs both stacks' pinned commands | PASS | `ci.yml` wiring + 3 independent live green GitHub Actions runs (31992452282, 32038510858, 32040002913) all executing ruff check/pytest/lint/vitest/build |
| Backend tests run against a live database, not a skip no-op | PASS | `services.postgres` + bootstrap + replay steps in `ci.yml`; live run 32038510858 confirmed `358 passed, 0 skipped`; reproduced locally this session: `422 passed`, zero `s` (skip) markers |
| RLS requirements exercised by dedicated tests, not prose | PASS | `test_rls_policies.py`, 64 tests covering anon/authenticated denial, privilege matrix, catalog views, soft-delete, internal view, service_role CRUD, grant-layer split, append-only trigger, storage matrix — all reproduced passing this session |

## TDD Compliance (Strict TDD active)

| Check | Result |
|---|---|
| TDD Evidence reported | Found — 4 "TDD Cycle Evidence" tables across all 4 batches in apply-progress.md |
| GREEN confirmed | All claimed-green tests reproduced passing in this session |
| Triangulation | Strong — parametrized 8/32/6/3/4/1/3/2/5 cases across roles×tables×privileges |
| Assertion quality | No tautologies, no ghost loops, no vacuous/mock-heavy tests found in `test_rls_policies.py` or `test_ci_workflow_safety.py`; every assertion exercises real Postgres or real regex/text checks against the real workflow file |

## SUGGESTION (non-blocking)

apply-progress.md has no dedicated "Batch 4/Phase 5" section (final regression) — that evidence lives directly in tasks.md's 5.1-5.4 Result notes instead. Not a functional gap, just an inconsistent artifact-organization pattern versus Batches 1-3.

## Issues Summary

- CRITICAL: 0
- WARNING: 1 (D5 self-verification baseline error — documentation/audit-trail accuracy only, no production code touched)
- SUGGESTION: 1 (apply-progress.md missing Phase 5 section, content exists in tasks.md instead)

**Recommendation**: safe to archive after (optionally) correcting design.md's File Changes table and apply-progress's PR1 wording re: frontend/src. No code change needed — the actual implementation is sound and fully spec-compliant.
