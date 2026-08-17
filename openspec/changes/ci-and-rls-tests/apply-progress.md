# Apply Progress: CI Pipeline + RLS Integration Tests

## Batch 1 of 4 (this batch): Phase 0 + Phase 1 — CI skeleton (PR 1)

**Mode**: Strict TDD (project-wide `strict_tdd: true`), applied where the
task is genuinely pytest-testable (task 1.1). Phase 0 and the YAML/workflow
tasks (1.2, 1.3) are infrastructure — verified by a real command run, not a
RED/GREEN pytest pair, per tasks.md's own note.

**Delivery**: chained PR slice, Work Unit 1 of 4 (`Suggested Work Units`
table in tasks.md). This batch's scope was pre-assigned by the launching
prompt as "PR 1 of 4" — the CI skeleton — and stays inside that unit's
boundary only. Phase 2 (Postgres service container + bootstrap SQL), Phase 3
(RLS module part A), Phase 4 (RLS module part B), and Phase 5 (final
combined verification) are explicitly **not** touched in this batch.

### Completed Tasks

- [x] 0.1 — Ran `uv run ruff format --check` from `backend/`. **Exit code 1**
      (non-zero): many pre-existing files under `backend/src/` and
      `backend/tests/` would be reformatted (unrelated pre-existing
      formatting drift, not introduced by this change). Per DD2a, the
      `ruff format --check` step was **omitted** from `ci.yml`. `ruff format`
      was **not** run to auto-fix — that would rewrite `backend/src/**`,
      forbidden by D5. See "Deferred Follow-up" below.
- [x] 1.1 — RED: wrote `backend/tests/architecture/test_ci_workflow_safety.py`
      (6 test functions, mirrors `test_frontend_service_role_boundary.py`'s
      static-text-check idiom). Ran against the not-yet-existing
      `.github/workflows/ci.yml` — all 6 tests failed with
      `AssertionError: missing CI workflow file`, confirming the harness
      genuinely exercises the file (not vacuous).
- [x] 1.2 — GREEN: created `.github/workflows/ci.yml`. Two parallel jobs
      (`backend`, `frontend`), no `needs:` between them. Triggers:
      `push` (branches: `[main]`), `pull_request` (branches: `[main]`),
      `workflow_dispatch` (DD3). `concurrency` group + `cancel-in-progress`.
      Top-level `permissions: contents: read`. `backend` job (no Postgres
      service in this batch — Phase 2's scope): checkout, `astral-sh/setup-uv@v5`
      (Python 3.13), `uv sync --locked`, `ruff check` (`if: ${{ !cancelled() }}`),
      `pytest -q` (`if: ${{ !cancelled() }}`) — no `ruff format --check` step
      (per 0.1's finding). `frontend` job: checkout, `actions/setup-node@v4`
      (Node 22, npm cache), `npm ci`, `eslint` / `vitest -- --run` /
      `next build` steps each `if: ${{ !cancelled() }}`, with
      `NEXT_PUBLIC_SUPABASE_URL: http://127.0.0.1:54321` and
      `NEXT_PUBLIC_SUPABASE_ANON_KEY: ci-placeholder-anon-key` set as
      job-level `env` (inline literals in the YAML, not GitHub Secrets, per D2).
      Re-ran 1.1's test file — all 6 pass.
- [x] 1.3 — GREEN: `openspec/config.yaml`'s
      `testing.quality_tools.type_checker` line changed from `"tsc --noEmit"`
      (a script that does not exist in `frontend/package.json`) to
      `"next build --webpack (Next-integrated tsc; no standalone tsc script)"`
      per DD2b. No other line in `config.yaml` touched.

### Not completed in this batch

- [ ] 1.4 — Verify via a real GitHub push/PR/`workflow_dispatch` run that
      both jobs go green end to end. **Cannot be performed by sdd-apply** —
      no live GitHub Actions trigger happens automatically in this session.
      This batch's local proof is: the YAML parses as valid YAML (sanity
      checked via an ephemeral `uv run --with pyyaml python -c "yaml.safe_load(...)"`,
      no dependency file changed), every command the workflow invokes was
      run locally with the results below, and the new static safety test is
      green. **Real "does it turn green in GitHub's UI" verification still
      requires the orchestrator to push/open a PR and check the Actions
      tab** — not claimed here.

### Deferred Follow-up (recorded, not actioned — outside this change's scope)

`uv run ruff format --check` is currently **non-zero** on the existing
`backend/` tree (pre-existing formatting drift across multiple
`backend/src/` and `backend/tests/` files, not introduced by this change).
The `ruff format --check` CI gate was intentionally left out of `ci.yml` in
this batch rather than either (a) running `ruff format` to silently rewrite
`backend/src/**` (forbidden by D5 — no application-code changes in this
change) or (b) shipping a gate that is red on its very first run (design.md
DD2a explicitly rejects this). **Recommended follow-up**: a separate,
dedicated formatting-only change that runs `ruff format` across `backend/`,
reviews the diff on its own, and then adds the `ruff format --check` step to
`ci.yml`.

### Files Changed

| File | Action | What Was Done |
|------|--------|----------------|
| `.github/workflows/ci.yml` | Created | First CI workflow. Two parallel jobs, DD3 triggers, no DB service yet (Phase 2's scope) |
| `backend/tests/architecture/test_ci_workflow_safety.py` | Created | 6 static tests: no `secrets.` token, no secret-shaped literal, no `pull_request_target`, `permissions:` present, no `github.event`/`head_ref` inside `run:` blocks, Supabase placeholders are safe loopback/non-JWT values |
| `openspec/config.yaml` | Modified | One line: `testing.quality_tools.type_checker` (DD2b) |
| `openspec/changes/ci-and-rls-tests/tasks.md` | Modified | Marked 0.1, 1.1, 1.2, 1.3 complete; 1.4 left open with a note explaining why |

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd backend && uv run pytest tests/architecture/test_ci_workflow_safety.py -v` → **6 passed** (RED confirmed first with the missing file: 6 failed with `AssertionError: missing CI workflow file`) |
| Runtime harness command/scenario and exact result | No local harness can execute GitHub Actions YAML. Nearest real-world proxy performed: `uv run --with pyyaml python -c "yaml.safe_load(open('.github/workflows/ci.yml'))"` → parses cleanly, `jobs: ['backend', 'frontend']`, `on keys: ['push', 'pull_request', 'workflow_dispatch']`. The real CI-run proof is task 1.4, deferred to the orchestrator's push/PR (see above) |
| Rollback boundary | Delete `.github/workflows/ci.yml` + `backend/tests/architecture/test_ci_workflow_safety.py` + revert the one `openspec/config.yaml` line. No other file touched; Phase 2-4 work (not started) is entirely independent of this rollback |

### TDD Cycle Evidence (Strict TDD)

| Task | RED | GREEN | REFACTOR |
|---|---|---|---|
| 1.1/1.2 `test_ci_workflow_safety.py` + `ci.yml` | Wrote the 6-test file against the not-yet-existing `.github/workflows/ci.yml`; ran `uv run pytest tests/architecture/test_ci_workflow_safety.py -v` → **6 failed**, each `AssertionError: missing CI workflow file` | Created `.github/workflows/ci.yml`; re-ran the same command → **6 passed** | Not needed — file matched the design.md interface contract (minus the omitted `ruff format --check` step) on first GREEN, no restructuring required |
| 0.1 / 1.3 (`config.yaml`, `ruff format --check` decision) | N/A — infrastructure/config task, not pytest-testable (tasks.md's own classification) | Verified by real command run (`uv run ruff format --check` exit code) and by re-reading the edited `config.yaml` line | N/A |

### Full-Suite Verification (this batch)

Ran with `DB_URL` **unset** — simulating this batch's CI environment (no
Postgres service yet; that is Phase 2's scope):

- `cd backend && uv run pytest tests/architecture/ -q` → **8 passed** (2
  pre-existing + 6 new safety tests)
- `cd backend && uv run pytest -q` (full suite, no `DB_URL`) → **293 passed,
  65 skipped, 0 failed**. All 65 skips are the pre-existing
  `pytest.skip("DB_URL not set -- run `npx supabase start`")` short-circuit
  in `conftest.py`'s `db_pool` fixture — expected and correct for this
  batch; Phase 2 is what wires a live Postgres service in so these stop
  skipping.
- `cd frontend && npm test -- --run` → **47 test files passed, 344 tests
  passed, 0 failed**
- `cd frontend && npx tsc --noEmit` → **exit 0, no errors** locally.
  **Caveat, not false confidence**: this local checkout already has
  `.next/types/` and `next-env.d.ts` on disk from prior local `next dev`/
  `next build` runs (both are gitignored per `frontend/.gitignore`). This is
  **not** the fresh-clone condition design.md's DD2b describes. A
  standalone `tsc --noEmit` on a genuinely fresh clone (no `.next/`, as CI
  always is) is expected to fail on `Cannot find name 'LayoutProps'`
  (`layout.tsx:26`), which is exactly why DD2b's decision — no standalone
  `tsc` step in CI, `next build` is the real type gate — was implemented as
  designed rather than "validated" by this local, non-fresh run.

### Deviations from Design

1. Per DD2a's binary apply-time precondition, `ruff format --check` was
   **omitted** from `ci.yml` because the local check exit non-zero (see
   "Deferred Follow-up" above). This is the explicitly-designed non-happy
   path, not a deviation from intent.
2. This batch's `ci.yml` intentionally does not yet include the
   `services.postgres` block, the bootstrap step, or the migration-replay
   step from design.md's full interfaces/contracts section — those belong
   to Phase 2 (PR 2), per the Suggested Work Units split. The `pytest -q`
   step runs today exactly as it will after Phase 2, just against a
   database-less environment where DB-dependent tests skip.

### Issues Found

None.

### Remaining Tasks (future batches — not started)

- [ ] Phase 2 (PR 2): Postgres service container + `supabase/ci/00_supabase_roles.sql`
      + `supabase/ci/01_storage_schema.sql` + migration-replay step wired
      into `ci.yml`; wires the ~15 pre-existing DB-integration test files in
      for real (tasks 2.1–2.6).
- [ ] Phase 3 (PR 3): `backend/tests/integration/db/test_rls_policies.py`
      part A — `as_role()` helper, denial tests, privilege matrix, catalog
      views, soft-delete, internal view (tasks 3.1–3.7).
- [ ] Phase 4 (PR 4): `test_rls_policies.py` part B — service_role CRUD,
      ledger grant-layer split, DD5 append-only two-layer proof, storage
      matrix (tasks 4.1–4.6).
- [ ] Phase 5: final combined regression across all 4 PRs + real GitHub
      Actions green-run confirmation (tasks 5.1–5.4).
- [ ] Task 1.4 specifically: confirm this batch's real GitHub Actions run
      goes green once pushed/dispatched by the orchestrator.

### Workload / PR Boundary

- Mode: chained PR slice (4 total), Work Unit 1 of 4
- Current work unit: "CI skeleton: workflow triggers/topology, frontend job
  (full), backend job without DB service, static safety test, config.yaml
  DD2b line" — exactly as scoped in tasks.md's `Suggested Work Units` table
- Boundary: starts from zero (no `.github/` existed) and ends with a
  green-locally, DB-less two-job workflow plus its static safety test; does
  not touch Postgres wiring, RLS tests, or any `backend/src`/`frontend/src`
  file
- Estimated review budget impact: `.github/workflows/ci.yml` (~55 lines),
  `test_ci_workflow_safety.py` (~157 lines), `openspec/config.yaml` (1 line)
  — well inside the 400-line budget on its own, as tasks.md's forecast
  intended for this slice

### Status

5/28 total tasks complete (0.1, 1.1–1.4). Phases 2–5 (23 tasks) remain for
future `sdd-apply` batches.

### PR 1 — Live CI Verification (orchestrator, post-apply)

Pushed `84f3eab`+`2080432` to `main`. First real run (31992223973) caught 3
genuine pre-existing latent bugs — none touched by this batch's own diff,
all exposed for the first time by actually running CI:

1. **Backend**: `ruff check` failed on an unused `Decimal` import in
   `test_admin_initial_stock.py` — `ruff check` had never run in CI before,
   so this had been silently accumulating.
2. **Frontend**: `stock-history.test.tsx`'s "changing the Since date input"
   test asserted a hardcoded `-03:00` offset without mocking
   `Date.prototype.getTimezoneOffset()` — passed only on a machine whose
   local timezone happens to be UTC-03 (the developer's), failed on the
   UTC GitHub Actions runner. A sibling test in the same file already had
   the correct mock; this one was missing it.
3. **Frontend**: `catalog-route-conformance.test.ts` pins a SHA256 of
   `runtime-caching.ts`'s raw bytes. The pinned hash was computed against
   CRLF line endings (Windows `core.autocrlf=true` materializes CRLF on
   disk), but the repository stores LF and Linux CI checks out LF
   unchanged — so the hash never matched on any non-Windows checkout.
   Fixed by normalizing CRLF→LF before hashing and re-pinning to the
   normalized value, making the pin OS-independent going forward.

All three fixed in `8b0cf22` (test-file-only changes, zero `backend/src`/
`frontend/src` touched, consistent with D5). Second run (31992452282) went
fully green on both jobs. Task 1.4 marked complete.

## PR 2 — Postgres Bootstrap (tasks 2.1-2.5, orchestrator)

**What**: Wired a `postgres:17` service container plus repo-owned CI
bootstrap into the backend job, so the ~15 pre-existing DB-integration test
files (silently skipping since inception, per `conftest.py`'s `DB_URL`
skip-guard) execute for real in CI.

**2.1 (manual RED, not committed)**: Started a throwaway bare `postgres:17`
container (`docker run ... -p 55432:5432 postgres:17`), copied the 5
`supabase/migrations/*.sql` files in, replayed them in lexicographic order
with `psql -v ON_ERROR_STOP=1` and no bootstrap. Failed exactly where
design.md's DD1 table predicted:
- `20260810000458_public_catalog_rls.sql:63` → `ERROR: role "service_role"
  does not exist`
- `20260810000502_storage_product_photos.sql:8` → `ERROR: relation
  "storage.buckets" does not exist`

**2.2/2.3 (GREEN)**: Wrote `supabase/ci/00_supabase_roles.sql` (creates
`anon`/`authenticated`/`service_role` with `service_role` granted
`bypassrls`, `grant usage on schema public`) and
`supabase/ci/01_storage_schema.sql` (minimal `storage.buckets`/
`storage.objects` stub, RLS enabled on both, broad grants matching
Supabase's real posture) — both verbatim from design.md's Interfaces/
Contracts section.

**2.4 (re-verify)**: Fresh container, bootstrap files applied first, then
all 5 migrations replayed — clean end to end, zero errors. Container
removed after verification (`docker rm -f ci_bare_pg17`), nothing left
running.

**2.5 (GREEN, ci.yml)**: Extended the `backend` job in
`.github/workflows/ci.yml` with `services.postgres` (`postgres:17`,
`pg_isready` health check, port 5432), `env.DB_URL`, a "Bootstrap
Supabase-managed roles and storage surface" step running both `psql -f`
commands, and a "Replay supabase/migrations" step (`for f in
supabase/migrations/*.sql`). Exact shape from design.md's Interfaces/
Contracts — nothing improvised.

**Local verification before push**:
- `uv run pytest backend/tests/architecture/test_ci_workflow_safety.py -v`
  — all 6 static safety tests still pass against the extended `ci.yml`
  (the new `DB_URL` env value and bootstrap/replay `run:` blocks contain no
  secret-shaped literal, no `${{ github.event`/`head_ref` interpolation).
- Full backend suite with `DB_URL` pointed at the local `supabase start`
  Postgres (`postgresql://postgres:postgres@127.0.0.1:54322/postgres`):
  **358 passed, 0 skipped** (vs. 293 passed / 65 skipped without `DB_URL`)
  — confirms the previously-dormant DB-backed files are healthy against a
  real Postgres before trusting the CI-only bootstrap stub.

**Task 2.6 (live verification)**: pushed (`2932d03` code, `31e2285` docs).
Run 32038510858 went fully green on both jobs on the **first** push — no
latent bugs this time, unlike PR 1. The `pytest` step log reads `358
passed, 2 warnings in 4.18s`, zero skips, exactly matching the local
`DB_URL`-set sanity run. Confirms the ~15 previously-dormant DB-integration
test files execute for real in CI now. No newly-surfaced failure, so no
follow-up needed per design's Risks section.

## Batch 2 of 4: Phase 3 — RLS module, part A (read boundary, PR 3)

**Mode**: Strict TDD (project-wide `strict_tdd: true`), applied via a
behavioral RED proof (see 3.1 below) rather than a classic "fails until
source is fixed" cycle — this is a proving test suite against
already-shipped RLS policies (D5 forbids any `backend/src/` change), so
there is no defect to fix. The equivalent TDD discipline here is proving the
harness is not vacuous before trusting any GREEN.

**Delivery**: chained PR slice, Work Unit 3 of 4 (`Suggested Work Units`
table in tasks.md). Scope pre-assigned as "PR 3 of 4" — RLS module part A —
and stays inside that unit's boundary only. Phase 4 (service_role CRUD,
ledger grant-layer split, DD5 append-only two-layer proof, storage matrix)
is explicitly **not** touched in this batch; Phases 1-2 were already
committed, pushed, and verified green on live GitHub Actions before this
batch started (see Batch 1 and PR 2 sections above).

### Completed Tasks

- [x] 3.1 — Created `backend/tests/integration/db/test_rls_policies.py`
      (new file) with the module docstring, `BASE_TABLES` / `CATALOG_VIEWS` /
      `RESTRICTED_ROLES` constants, and the `as_role()` SAVEPOINT helper —
      verbatim from design.md's Interfaces/Contracts section. **Deviation
      note**: the task's literal instruction ("run locally against a
      bootstrap missing `bypassrls`") describes a Phase 4/service_role
      concern (design.md DD1's load-bearing `bypassrls` detail matters only
      for `service_role`'s CRUD tests, added in Phase 4). It does not apply
      to Part A, whose only role-switch tests are `anon`/`authenticated`
      denial — neither role ever has `bypassrls`, so removing it from a
      bootstrap changes nothing they can observe. The local instance is also
      the real `supabase start` stack (confirmed via `npx supabase status`:
      `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres`),
      not the CI-only `supabase/ci/00_supabase_roles.sql` bootstrap from
      Phase 2 — there is no "missing bypassrls" variant of it to run
      against locally without mutating an already-shipped Phase 2 file,
      which is out of this batch's scope. Substituted the equivalent proof:
      temporarily commented out the `SET LOCAL ROLE "{role}"` line inside
      `as_role()` and re-ran every test that depends on it behaviorally (the
      8 base-table denial tests + the 2 `variant_stock_levels` denial
      tests) — all 10 failed with `Failed: DID NOT RAISE
      InsufficientPrivilegeError` (the superuser `db_conn` connection can
      read anything without the role switch), proving the harness
      genuinely exercises Postgres's RLS/grant enforcement rather than
      passing vacuously. Reverted the line immediately after; the file
      committed contains no trace of the temporary edit.
- [x] 3.2 — Denial test `test_restricted_role_select_denied_on_base_table`,
      parametrized 2 roles × 4 `BASE_TABLES` = 8 cases, each
      `pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError)` inside
      `as_role`. 8/8 passed first run (zero policies + zero grants on all 4
      base tables, already shipped).
- [x] 3.3 — Privilege-matrix test
      `test_restricted_role_has_no_privilege_on_base_table`, parametrized 2
      roles × 4 tables × 4 privileges (`select`/`insert`/`update`/`delete`)
      = 32 cases, `SELECT has_table_privilege($1, $2, $3)` asserted `False`
      — no `SET ROLE` needed per design.md. 32/32 passed.
- [x] 3.4 — Catalog-view test
      `test_restricted_role_can_read_seeded_row_from_catalog_view`: seeds
      one product + variant + hero image as superuser via `db_conn`
      (`PostgresProductRepository.add` + a raw-SQL `product_images` insert,
      mirroring `test_catalog_soft_delete_views.py`'s existing pattern),
      then under `as_role` for both roles asserts `count(*) == 1` on each of
      the 3 `CATALOG_VIEWS`, parametrized 2 roles × 3 views = 6 cases. 6/6
      passed.
- [x] 3.5 — Three soft-delete test functions, all reading through
      `as_role(db_conn, "anon")` after a superuser `UPDATE ... SET
      deleted_at = now()`:
      `test_retiring_the_product_hides_it_from_all_three_views_for_anon`,
      `test_retiring_one_variant_hides_only_that_variant_and_its_image_for_anon`,
      `test_a_live_sibling_product_stays_visible_to_anon_after_a_retirement`.
      3/3 passed.
- [x] 3.6 — Internal-view tests for `variant_stock_levels`:
      `test_restricted_role_has_no_select_privilege_on_variant_stock_levels`
      (`has_table_privilege` False, parametrized 2 roles) and
      `test_restricted_role_is_denied_reading_variant_stock_levels`
      (behavioral denial under `as_role`, parametrized 2 roles). 4/4 passed.
- [x] 3.7 — Verify: `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
      uv run pytest backend/tests/integration/db/test_rls_policies.py -v` →
      **53 passed** (8 + 32 + 6 + 3 + 4 = 53, matches the file's full
      parametrized count exactly). Full backend suite with the same
      `DB_URL`: **411 passed, 0 failed** (358 pre-existing from PR 2's
      verification + 53 new). Confirmed zero leftover rows by querying
      `docker exec supabase_db_SistemaGCELL psql -U postgres -c "SELECT
      count(*) FROM products WHERE slug LIKE 'funda-rls-%'"` directly after
      the full run — **0 rows** — confirming `db_conn`'s outer-transaction
      rollback (unmodified, per D5/DD4) leaves no trace, not just assuming
      it. `uv run ruff check tests/integration/db/test_rls_policies.py` →
      **All checks passed!**

### Files Changed

| File | Action | What Was Done |
|------|--------|----------------|
| `backend/tests/integration/db/test_rls_policies.py` | Created | `as_role()` SAVEPOINT helper + 53 parametrized tests: base-table denial (8), privilege matrix (32), catalog views (6), soft-delete (3), internal view (4) |
| `openspec/changes/ci-and-rls-tests/tasks.md` | Modified | Marked 3.1–3.7 complete with per-task Result notes |

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest backend/tests/integration/db/test_rls_policies.py -v` (from repo root) → **53 passed** |
| Runtime harness command/scenario and exact result | Real local `supabase start` Postgres (confirmed running via `docker ps` — `supabase_db_SistemaGCELL` present — and `npx supabase status`), not a mock or stub. Every assertion executes actual `SET LOCAL ROLE` / RLS / grant enforcement against real Postgres system catalogs. Full backend suite against the same instance: `cd backend && DB_URL=... uv run pytest -q` → **411 passed, 0 failed** |
| Rollback boundary | Delete `backend/tests/integration/db/test_rls_policies.py`; no other file touched in this batch. `db_conn`'s existing per-test transaction rollback (unchanged, D5/DD4) means no schema, policy, grant, or data change is left behind by any test run — verified directly via `psql` row count, not assumed |

### TDD Cycle Evidence (Strict TDD)

| Task | RED | GREEN | REFACTOR |
|---|---|---|---|
| 3.1–3.2 (`as_role()` + base-table denial) | Temporarily disabled `SET LOCAL ROLE` inside `as_role()`; ran the 8 base-table denial tests → **8 failed**, each `Failed: DID NOT RAISE InsufficientPrivilegeError` (superuser bypasses without the role switch) | Reverted the line; re-ran → **8 passed** | Not needed — `as_role()` matched design.md's Interfaces/Contracts verbatim on first correct GREEN |
| 3.6 (`variant_stock_levels` behavioral denial) | Same disabled-role-switch run also covered the 2 `variant_stock_levels` denial tests → **2 failed**, same `DID NOT RAISE` | Reverted; re-ran → **2 passed** | Not needed |
| 3.3 (privilege matrix) | N/A — pure SQL-function assertion (`has_table_privilege`), no `SET ROLE`/`as_role()` dependency to prove non-vacuous; correctness is exact (`False` for a role with zero grants is unconditionally true, not a behavior that a broken harness could fake) | 32/32 passed against the already-shipped grant state | N/A |
| 3.4–3.5 (catalog views + soft delete) | Implicitly covered by the same `as_role()` proof above — these tests share the identical role-switch mechanism already proven genuine in 3.1/3.2/3.6; no separate isolated RED needed for read-success assertions (a broken `as_role()` that never switches role would still show `count == 1` as superuser, so the meaningful RED for this direction is the *denial* tests failing when the switch is real but misapplied — not applicable here since the seed rows genuinely exist and are genuinely visible through the view's own `WHERE deleted_at IS NULL` predicate, independent of role) | 6/6 + 3/3 passed | Not needed |

### Deviations from Design

1. Task 3.1's literal "bootstrap missing `bypassrls`" RED instruction does
   not map cleanly onto Part A's scope (anon/authenticated only); documented
   above under 3.1 and in tasks.md's Result note. The substituted proof
   (disable `SET LOCAL ROLE`, confirm all role-dependent denial tests fail)
   is a strictly more direct test of the exact mechanism `as_role()`
   provides, and required no modification of any already-shipped Phase
   1/2 file.
2. None otherwise — implementation matches design.md's Interfaces/Contracts
   section for `test_rls_policies.py` exactly (constants, `as_role()` body,
   parametrization shapes).

### Issues Found

None.

### Remaining Tasks (future batches — not started)

- [ ] Phase 4 (PR 4): `test_rls_policies.py` part B — service_role CRUD,
      ledger grant-layer split, DD5 append-only two-layer proof, storage
      matrix (tasks 4.1–4.6).
- [ ] Phase 5: final combined regression across all 4 PRs + real GitHub
      Actions green-run confirmation (tasks 5.1–5.4).

### Workload / PR Boundary

- Mode: chained PR slice (4 total), Work Unit 3 of 4
- Current work unit: "RLS module part A: `as_role()` helper +
  anon/authenticated denial, privilege matrix, catalog views, soft delete,
  internal view" — exactly as scoped in tasks.md's `Suggested Work Units`
  table
- Boundary: starts from zero (`test_rls_policies.py` did not exist) and ends
  with a green, self-contained, non-vacuously-proven read-boundary RLS test
  module; does not touch `service_role`, storage, the append-only trigger,
  or any `backend/src`/`frontend/src`/`.github/workflows` file
- Estimated review budget impact: `test_rls_policies.py` is ~340 lines new
  — inside the 400-line budget on its own, matching tasks.md's forecast for
  this slice (the forecast's 450-550 line range was for the *full* module
  including Phase 4's part B, not this slice alone)

### Status

18/28 total tasks complete (0.1, 1.1–1.4, 2.1–2.6, 3.1–3.7). Phase 4 (6
tasks) and Phase 5 (4 tasks) remain for future `sdd-apply` batches.

## Batch 3 of 4: Phase 4 — RLS module, part B (service_role + storage, PR 4)

**Mode**: Strict TDD (project-wide `strict_tdd: true`), same proving-suite
discipline as Batch 2 (PR 3): this batch tests already-shipped RLS
policies/grants/triggers (D5 forbids any `backend/src/` change), so there is
no defect to fix. RED is a non-vacuousness proof of the exact mechanism under
test (`BYPASSRLS`'s load-bearing role), executed manually and reverted, not a
committed failing test.

**Delivery**: chained PR slice, Work Unit 4 of 4 (final content PR in the
chain). Scope pre-assigned as "PR 4 of 4" — RLS module part B — and stays
inside that unit's boundary only. Phase 5 (final combined regression across
all 4 PRs + live GitHub Actions confirmation) is explicitly **not** touched
in this batch — that is the orchestrator's job next. Phases 1–3 were already
committed and (for PR1/PR2) pushed and verified green on live GitHub Actions
before this batch started (see Batch 1, PR 2, and Batch 2 sections above);
PR 3 (`6c8e3cb`+`574c88c`) was committed locally but not yet pushed per the
launch prompt.

### Completed Tasks

- [x] 4.1 — RED, non-committed proof that `BYPASSRLS` is load-bearing for
      the service_role CRUD test, without mutating the real local
      `service_role` role. Inside a transaction rolled back at the end
      (never committed): created a brand-new role `rls_proof_no_bypass` with
      the *identical* explicit GRANTs `service_role` has on
      `products`/`product_variants`/`product_images` (`select, insert,
      update, delete` + `usage on schema public`) but **without**
      `bypassrls`, then attempted the same `INSERT` under it via `SET LOCAL
      ROLE`. Result:
      `ERROR: new row violates row-level security policy for table
      "products"` — the GRANT alone is insufficient; the base tables have
      RLS enabled with zero policies, so only `BYPASSRLS` (which the real
      `service_role` role carries) lets the CRUD test's INSERT succeed.
      Confirmed via `SELECT rolname FROM pg_roles WHERE rolname =
      'rls_proof_no_bypass'` returning 0 rows after `ROLLBACK` — `CREATE
      ROLE`/`GRANT` are transactional DDL, so the temporary role and its
      grants left no trace and the real `service_role` role was never
      touched, satisfying the launch prompt's constraint directly (this is
      the analogous substitute for PR3's "disable `SET LOCAL ROLE`
      temporarily" RED proof — same non-vacuousness goal, adapted to a
      claim about a role *attribute* rather than the role-switch mechanism
      itself). A secondary finding surfaced along the way: the local
      `postgres` connection role is **not** a literal Postgres superuser
      (`rolsuper = false`); it has `rolbypassrls = true` and
      `rolcreaterole = true` instead (Supabase's convention). `SET ROLE` to
      an arbitrary newly-created role therefore needs an explicit `GRANT
      <role> TO postgres` first — membership, not superuser status, is what
      authorizes it. This has no effect on any existing `as_role()` call
      (`anon`/`authenticated`/`service_role` are already granted to
      `postgres` by Supabase's own bootstrap), so no other test needed any
      change.
- [x] 4.2 — GREEN:
      `test_service_role_full_crud_on_products_variants_and_images` — one
      test performing INSERT → SELECT(assert) → UPDATE → SELECT(assert) →
      DELETE → SELECT(assert) on `products`/`product_variants`/
      `product_images`, all inside a single `as_role(db_conn,
      PRIVILEGED_ROLE)` block. Doing the full chain in one block is
      required, not stylistic: `as_role()`'s `finally: await
      savepoint.rollback()` always discards the block's writes on exit
      (see its docstring), so a write made in one `as_role` call is
      invisible to a later, separate `as_role` call — verified this
      behavior directly against the file's own existing pattern (Part A's
      writes always happen via `db_conn` *outside* `as_role`, reads happen
      inside it) before designing this test. 1/1 passed.
- [x] 4.3 — GREEN, 3 tests for the `stock_movements` grant-layer split (DD5
      #1): `test_service_role_select_and_insert_succeed_on_stock_movements`
      (INSERT + count-assert inside one `as_role` block),
      `test_service_role_update_denied_on_stock_movements` and
      `test_service_role_delete_denied_on_stock_movements` (each seeds a
      real row as superuser first, then attempts the denied statement under
      a fresh `as_role(db_conn, PRIVILEGED_ROLE)` block, asserting
      `asyncpg.exceptions.InsufficientPrivilegeError`). 3/3 passed —
      confirms `service_role` is stopped by the missing `GRANT`
      (`20260810000458_public_catalog_rls.sql:65` grants only `select,
      insert`), one layer above the trigger, exactly as DD5 states.
- [x] 4.4 — GREEN, 2 tests for the append-only trigger itself (DD5 #2):
      `test_owner_update_denied_by_append_only_trigger_on_stock_movements`
      and `test_owner_delete_denied_by_append_only_trigger_on_stock_movements`,
      both using `db_conn` directly (the owner/superuser connection — never
      `as_role`, per DD5's explicit distinction: `service_role` never
      reaches this layer, it is stopped earlier by 4.3's grant-layer test).
      Each wraps `pytest.raises(asyncpg.exceptions.RaiseError,
      match="append-only")` **around** an `async with db_conn.transaction():`
      block (not inside it) — deliberate ordering: letting the trigger's
      exception propagate out of the nested-transaction context manager is
      what makes `Transaction.__aexit__` issue `ROLLBACK TO SAVEPOINT`
      instead of the default commit-on-clean-exit path, which would itself
      fail (`RELEASE SAVEPOINT` is not permitted once the sub-transaction is
      aborted). Verified this reasoning against `as_role()`'s own design (it
      avoids the same trap by never relying on the context manager's default
      exit — it always explicitly rolls back in a `finally` block instead).
      2/2 passed.
- [x] 4.5 — GREEN, 5 tests for the `storage.objects` matrix: seeded via a
      new `_seed_two_bucket_storage_objects()` helper (superuser, real
      `product-photos` bucket + one new unrelated bucket, one object each,
      unique names via `uuid4().hex[:8]` so scoping is asserted by object
      identity, not just a row count).
      `test_anon_reads_only_product_photos_bucket_objects`,
      `test_anon_insert_denied_on_storage_objects`,
      `test_anon_update_affects_zero_rows_on_storage_objects`,
      `test_anon_delete_affects_zero_rows_on_storage_objects`,
      `test_service_role_insert_succeeds_on_storage_objects`. 5/5 passed.
      **Discovered and documented a local-only fidelity gap not covered by
      CI's minimal stub (design.md DD1's own named "documented fidelity
      gap")**: the real local Supabase Storage schema installs a
      statement-level `BEFORE DELETE` trigger
      (`storage.protect_objects_delete` → `storage.protect_delete()`) that
      raises `Direct deletion from storage tables is not allowed. Use the
      Storage API instead.` (SQLSTATE 42501, same class as
      `InsufficientPrivilegeError`) for **any** direct `DELETE` on
      `storage.objects`, from **any** role, unless the session sets
      `storage.allow_delete_query = 'true'` — verified this experimentally
      with raw `psql` (`SET LOCAL ROLE anon; DELETE ...` → the guard error;
      then `SET LOCAL storage.allow_delete_query = 'true'; DELETE ...` →
      `DELETE 0`, the real RLS-layer result) *before* writing the
      permanent test, to avoid asserting the wrong layer under a
      same-SQLSTATE coincidence. The permanent
      `test_anon_delete_affects_zero_rows_on_storage_objects` sets that GUC
      before the DELETE, with a docstring explaining why: it neutralizes a
      local-only Storage-*service* safety net (not present in CI's `01_
      storage_schema.sql` stub, which has no such trigger), so the
      assertion proves the RLS policy layer identically on both
      environments — an unrecognized two-part custom GUC name is a
      harmless, silently-accepted no-op placeholder in vanilla Postgres,
      so setting it on CI (where the trigger doesn't exist) changes
      nothing.
- [x] 4.6 — Verify. `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres
      uv run pytest backend/tests/integration/db/test_rls_policies.py -v` →
      **64 passed** (53 Part A + 11 Part B, matches the file's full test
      count exactly). Full backend suite, same `DB_URL`:
      **422 passed, 0 failed** (411 pre-existing from Batch 2 + 11 new).
      `uv run ruff check tests/integration/db/test_rls_policies.py` → all
      checks passed. Confirmed **zero leftover rows** directly (not
      assumed) via `docker exec supabase_db_SistemaGCELL psql`: `SELECT
      count(*) FROM products WHERE slug LIKE 'funda-rls-%'` → 0; `SELECT
      count(*) FROM stock_movements WHERE reason = 'oops'` → 0; `SELECT
      count(*) FROM storage.buckets WHERE id LIKE 'rls-test-%'` → 0;
      `SELECT count(*) FROM storage.objects WHERE name LIKE 'rls-test-%'`
      → 0 — confirms `db_conn`'s per-test transaction rollback (unmodified,
      D5/DD4) leaves no trace across every new table/schema this batch
      touched, including `storage`. **The "confirm CI actually runs it"
      half of D4 is deferred to the orchestrator** — this batch has no
      GitHub push/`workflow_dispatch` access, the same deferral pattern
      used for PR1's task 1.4.

### Files Changed

| File | Action | What Was Done |
|------|--------|----------------|
| `backend/tests/integration/db/test_rls_policies.py` | Modified (appended) | Added `PRIVILEGED_ROLE` constant, `_seed_two_bucket_storage_objects()` helper, and 11 Part B tests: service_role full CRUD (1), stock_movements grant-layer split (3), append-only trigger owner-layer (2), storage.objects matrix (5). Updated module docstring to describe Part B instead of deferring it |
| `openspec/changes/ci-and-rls-tests/tasks.md` | Modified | Marked 4.1–4.6 complete with per-task Result notes; 4.6's CI-confirmation half noted as deferred to the orchestrator |

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest backend/tests/integration/db/test_rls_policies.py -v` (from repo root) → **64 passed** (53 pre-existing + 11 new) |
| Runtime harness command/scenario and exact result | Real local `supabase start` Postgres (confirmed via `docker ps` — `supabase_db_SistemaGCELL healthy` — same instance Batch 2 used). Every assertion executes actual `SET LOCAL ROLE` / RLS / GRANT / trigger enforcement against real Postgres, including a real local-only Storage-service trigger discovered and documented above. Full backend suite against the same instance: `cd backend && DB_URL=... uv run pytest -q` → **422 passed, 0 failed** |
| Rollback boundary | Revert the appended block in `backend/tests/integration/db/test_rls_policies.py` (11 tests + 1 constant + 1 helper + docstring update); no other file touched in this batch. `db_conn`'s existing per-test transaction rollback (unchanged, D5/DD4) means no schema, policy, grant, trigger, or data change is left behind by any test run — verified directly via `psql` row counts across `products`, `stock_movements`, `storage.buckets`, and `storage.objects`, not assumed |

### TDD Cycle Evidence (Strict TDD)

| Task | RED | GREEN | REFACTOR |
|---|---|---|---|
| 4.1–4.2 (service_role CRUD, `BYPASSRLS` proof) | Created a temporary, fully-reversible role (`rls_proof_no_bypass`) inside a rolled-back transaction with `service_role`'s exact GRANTs minus `bypassrls`; attempted the same INSERT → **failed**, `ERROR: new row violates row-level security policy for table "products"`. Confirmed the temp role left zero trace after rollback (`pg_roles` count 0) — the real `service_role` role was never mutated | Wrote the permanent CRUD test against the real, unmodified `service_role` role; ran it → **1 passed** | Not needed — single cohesive test, no restructuring required |
| 4.3 (stock_movements grant-layer split) | N/A as a separate RED — this is a proving suite against an already-shipped GRANT statement (`grant select, insert on stock_movements to service_role`, no update/delete), same category as Part A's privilege-matrix tests: the expected denial is unconditionally true given the shipped grant, not a behavior a broken harness could fake vacuously (a broken `as_role()` would already have failed Part A's 3.1 non-vacuousness proof) | 3/3 passed on first run | Not needed |
| 4.4 (append-only trigger, owner layer) | N/A as a separate RED — proving an already-shipped `BEFORE UPDATE OR DELETE` trigger (`reject_stock_movements_mutation`) whose exception message is asserted verbatim (`match="append-only"`); the trigger's existence is what makes the test genuine, and it is exercised via `db_conn` directly (not `as_role`), so Part A's role-switch non-vacuousness proof does not apply here — the non-vacuousness argument instead comes from executing the actual `UPDATE`/`DELETE` statement and asserting the real exception type + message, which a no-op or misconfigured test could not fake | 2/2 passed on first run | Not needed |
| 4.5 (storage.objects matrix) | Ran the exact `SELECT`/`INSERT`/`UPDATE`/`DELETE` sequence manually via raw `psql` with `SET LOCAL ROLE` **before** writing the permanent test, specifically to discover whether the local Storage schema's extra `protect_delete` trigger would produce a different (and misleading, same-SQLSTATE) failure mode than the RLS policy under test — it did, and the manual proof is what surfaced the `storage.allow_delete_query` GUC as the correct, non-committed way to neutralize it | 5/5 passed after adding the GUC-set line to the DELETE test | Not needed |

### Deviations from Design

1. Task 4.1's literal instruction implied a committed/permanent RED test
   ("confirm the service_role CRUD test fails without bypassrls present").
   As with Batch 2's task 3.1, this cannot be done by mutating the real,
   shared local `service_role` role (explicitly disallowed by the launch
   prompt) or by shipping a temporary-but-committed test that manipulates
   role attributes as part of the permanent suite. Substituted a manual,
   fully-reversible, non-committed proof using a throwaway role with
   `service_role`'s exact grants minus `bypassrls`, documented in tasks.md
   and here. This is the same category of substitution PR3 used for its own
   analogous local-vs-CI-only constraint, applied to a different claim
   (role attribute vs. role-switch mechanism).
2. Design.md's Testing Strategy table describes the storage tests generically
   ("`UPDATE`/`DELETE` affect 0 rows") without anticipating the real local
   Supabase Storage schema's `protect_delete` statement-level trigger — a
   genuine discovery during this batch, not present in CI's minimal stub
   (DD1's own named, expected fidelity gap between the stub and a real
   Supabase instance). Handled by setting `storage.allow_delete_query =
   'true'` inside the `anon` DELETE test's `as_role` block, with a docstring
   explaining the divergence and why the fix is portable to CI without
   changing test meaning there.
3. None otherwise — implementation matches design.md's DD5 two-layer
   append-only proof, the stock_movements grant-layer split, and the
   storage matrix exactly as specified.

### Issues Found

None — both discoveries above (the `postgres` role's non-superuser status
locally, and the local-only `protect_delete` trigger) are pre-existing
environment facts, not regressions, and both are fully documented and
worked around without touching `backend/src/**`, `supabase/migrations/**`,
or any already-shipped Phase 1–3 file.

### Remaining Tasks (future batch — orchestrator)

- [ ] Phase 5: final combined regression across all 4 PRs + real GitHub
      Actions green-run confirmation (tasks 5.1–5.4) — explicitly out of
      this batch's scope per the launch prompt.
- [ ] Task 4.6's CI-confirmation half: verify the real CI workflow
      (Phase 2's `ci.yml`) actually executes these 11 new Part B tests once
      pushed — deferred to the orchestrator, no GitHub push/dispatch access
      in this batch.

### Workload / PR Boundary

- Mode: chained PR slice (4 total), Work Unit 4 of 4 (final content PR)
- Current work unit: "RLS module part B: service_role CRUD, ledger
  grant-layer split, DD5 append-only two-layer proof, storage.objects
  matrix" — exactly as scoped in tasks.md's `Suggested Work Units` table
- Boundary: starts from the 53-test Part A module (unchanged) and ends with
  the full 64-test module; does not touch `backend/src`, `frontend/src`,
  `.github/workflows`, `supabase/ci/`, or `supabase/migrations`
- Estimated review budget impact: the appended block is ~330 lines
  (constant + helper + 11 tests + docstring update) — inside the 400-line
  budget on its own, matching tasks.md's forecast for this slice (the
  forecast's 450–550 line range was for the *full* module including Part
  A, already delivered in PR 3)

### Status

24/28 total tasks complete (0.1, 1.1–1.4, 2.1–2.6, 3.1–3.7, 4.1–4.6). Phase 5
(4 tasks: 5.1–5.4) remains — orchestrator's scope per the launch prompt, not
this batch's.
