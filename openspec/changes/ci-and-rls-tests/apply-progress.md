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

**Task 2.6 (live verification)**: pending — requires pushing to a real
GitHub Actions run, same "push and verify" pattern as PR 1.
