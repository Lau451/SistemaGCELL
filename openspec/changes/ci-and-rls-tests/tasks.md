# Tasks: CI Pipeline + RLS Integration Tests

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~650-800 total (ci.yml ~65-90, 00_supabase_roles.sql ~12, 01_storage_schema.sql ~35, test_ci_workflow_safety.py ~80-100, test_rls_policies.py ~450-550, config.yaml 1) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | 4 work units (below) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending — user must choose |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

Rationale: `test_rls_policies.py` alone (`as_role()` helper + ~14 parametrized
tests across 2 restricted roles × 4 base tables × 4 privileges, 3 catalog
views, 3 soft-delete cases, 1 internal view, service_role CRUD on 3 tables,
the ledger grant-layer split, the DD5 two-layer append-only proof, and a
2-bucket storage matrix) is comparable in shape to the existing
`test_stock_movement_repository.py` (375 lines) but covers strictly more
surface — realistic range 450-550 lines, already over budget by itself. Added
to a first-ever ~65-90-line workflow file, two new bootstrap SQL files, and a
new static safety test, a single PR is not viable. This confirms the
proposal's own "Medium, real chaining risk" flag and resolves it toward
**Yes**, extending the proposal's 3 named slices to 4 by splitting the RLS
module in two (a single ~500-line test-only PR is still reviewer-hostile even
though it is not production code).

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | CI skeleton: workflow triggers/topology, frontend job (full), backend job without DB service (lint+format+pytest against the still-skipping suite), static safety test, config.yaml DD2b line | PR 1 | `uv run pytest backend/tests/architecture/test_ci_workflow_safety.py -v` | `workflow_dispatch`/PR run of the real GitHub Actions workflow (no local harness can validate YAML) | Delete `.github/workflows/ci.yml` + `test_ci_workflow_safety.py` + revert `config.yaml` line; no other file touched |
| 2 | Postgres service container + `supabase/ci/*.sql` bootstrap + migration replay wired into ci.yml; wires the ~15 pre-existing DB test files in for real | PR 2 | `cd backend && uv run pytest -q` (full suite, confirms zero skips) | `postgres:17` container in the actual CI job (manual local replay first, per 2.1) | Revert the `services.postgres`/bootstrap/replay diff in ci.yml + delete the two `supabase/ci/*.sql` files; PR 1's skeleton keeps working stand-alone |
| 3 | RLS module part A: `as_role()` helper + anon/authenticated denial, privilege matrix, catalog views, soft delete, internal view | PR 3 | `uv run pytest backend/tests/integration/db/test_rls_policies.py -v` | Local `supabase start` Postgres via `db_conn`; then the CI Postgres service from PR 2 | Delete `test_rls_policies.py`; PR 2's wiring and existing DB tests unaffected |
| 4 | RLS module part B: service_role CRUD, ledger grant-layer split, DD5 append-only two-layer proof, storage.objects matrix | PR 4 | `uv run pytest backend/tests/integration/db/test_rls_policies.py -v` (full file) | Same as PR 3 | Revert the part-B test functions appended to `test_rls_policies.py`; part A stays green |

## Phase 0: Apply-time precondition (DD2a)

- [x] 0.1 Run `uv run ruff format --check` from `backend/`. Exit 0 → keep the
      `ruff format --check` step in Phase 1's workflow. Non-zero → omit that
      step from `ci.yml` and record a follow-up; never run `ruff format`
      (would rewrite `backend/src/`, forbidden by D5).
      **Result: non-zero (many pre-existing files would be reformatted).
      Step omitted from `ci.yml`; follow-up recorded in apply-progress.md.**

## Phase 1: CI skeleton — PR 1 (no DB)

- [x] 1.1 RED `backend/tests/architecture/test_ci_workflow_safety.py` (new,
      mirrors `test_frontend_service_role_boundary.py`'s static-grep
      pattern) — read `.github/workflows/ci.yml` as text; assert no
      `${{ secrets.` token, no `pull_request_target` trigger, no
      `${{ github.event` / `github.head_ref` inside any `run:` block,
      `permissions:` key present, `NEXT_PUBLIC_SUPABASE_URL` value is
      loopback (`127.0.0.1`), never `*.supabase.co`. Run against the
      missing file first — fails.
- [x] 1.2 GREEN `.github/workflows/ci.yml` (new) — `name: CI`; `push`
      (branches: [main]) / `pull_request` (branches: [main]) /
      `workflow_dispatch` (DD3); `concurrency` group + `cancel-in-progress`;
      top-level `permissions: contents: read`. `frontend` job complete
      (checkout, `setup-node@v4` node 22 + npm cache, `npm ci`, `eslint` /
      `vitest -- --run` / `next build` steps each `if: ${{ !cancelled() }}`,
      loopback env per D2). `backend` job in this phase has **no** Postgres
      service/bootstrap/replay yet: checkout, `setup-uv@v5` (3.13),
      `uv sync --locked`, `ruff check`, conditionally `ruff format --check`
      (per 0.1), `pytest -q` — still green because `DB_URL` stays unset.
      Confirm 1.1 now passes.
- [x] 1.3 GREEN `openspec/config.yaml` — replace `testing.quality_tools.type_checker`
      value with the literal DD2b line (Next-integrated tsc note); no other
      line touched.
- [ ] 1.4 Verify (workflow's own proof, not RED/GREEN): push/dispatch a real
      run and confirm both jobs go green end to end. **Pending — requires an
      actual GitHub push/PR/dispatch, which sdd-apply cannot perform.**

## Phase 2: Postgres bootstrap — PR 2 (wires EXISTING DB tests in)

- [ ] 2.1 RED (manual, not committed) — start a bare `postgres:17` container,
      replay `supabase/migrations/*.sql` with `psql` directly, no bootstrap.
      Confirm it fails exactly where design.md's DD1 table says: missing
      `service_role`/`anon`/`authenticated` at `20260810000458`, then the
      missing `storage` schema at `20260810000502`.
- [ ] 2.2 GREEN `supabase/ci/00_supabase_roles.sql` (new, CI-only, not a
      migration) — literal content from design.md: `anon`, `authenticated`
      (nologin noinherit), `service_role` (nologin noinherit **bypassrls**),
      `grant usage on schema public to anon, authenticated, service_role`.
- [ ] 2.3 GREEN `supabase/ci/01_storage_schema.sql` (new, CI-only) — literal
      content: `create schema storage`; `storage.buckets` / `storage.objects`
      tables; RLS enabled on both; broad grants to `anon`/`authenticated`/
      `service_role` (policy restricts, not the grant, per design).
- [ ] 2.4 Re-run 2.1's manual replay with both bootstrap files applied first
      — confirm all 5 migrations replay clean end to end.
- [ ] 2.5 Extend `.github/workflows/ci.yml` backend job — add
      `services.postgres` (`postgres:17`, health-checked), `env.DB_URL`, a
      "Bootstrap Supabase-managed roles and storage surface" step
      (`psql -f supabase/ci/00_supabase_roles.sql` then `01_storage_schema.sql`),
      and a "Replay supabase/migrations" step
      (`for f in supabase/migrations/*.sql; do psql -f "$f"; done`) — exact
      shape from design.md's Interfaces/Contracts.
- [ ] 2.6 Verify in a real PR/dispatch run: `db_pool` no longer skips — the
      ~15 pre-existing DB-integration files execute for real. Per design's
      Risks: fix a newly-surfaced failure only if it touches nothing under
      `backend/src/`; otherwise document as a follow-up, do not expand scope.

## Phase 3: RLS module, part A — PR 3 (read boundary)

- [ ] 3.1 RED `backend/tests/integration/db/test_rls_policies.py` (new) —
      module docstring; `BASE_TABLES` / `CATALOG_VIEWS` / `RESTRICTED_ROLES`
      constants; `as_role()` async context manager (SAVEPOINT via
      `conn.transaction()`, `SET LOCAL ROLE "{role}"`, literal-only role
      input per Threat Matrix). Run locally against a bootstrap missing
      `bypassrls` to confirm the harness genuinely fails, not vacuously.
- [ ] 3.2 GREEN — denial test: `anon`/`authenticated` `SELECT` denied on all
      4 `BASE_TABLES`, parametrized 2×4, `pytest.raises(InsufficientPrivilegeError)`
      via `as_role`.
- [ ] 3.3 GREEN — privilege-matrix test: `SELECT has_table_privilege($1,$2,$3)`
      is `False` for both restricted roles × 4 base tables ×
      {select, insert, update, delete}, parametrized 2×4×4.
- [ ] 3.4 GREEN — catalog-view test: seed one product/variant/image as
      superuser via `db_conn`; under `as_role` for both roles assert
      `count(*) == 1` on each of the 3 `CATALOG_VIEWS`.
- [ ] 3.5 GREEN — soft-delete tests (3 functions, reuse 3.4's seed): retiring
      the product hides it from all 3 views for `anon`; retiring one variant
      hides only that variant + its image; a live sibling stays visible.
- [ ] 3.6 GREEN — internal-view test: `variant_stock_levels` unreadable by
      `anon`/`authenticated` — `has_table_privilege` False plus behavioral
      denial under `as_role`.
- [ ] 3.7 Verify: `uv run pytest backend/tests/integration/db/test_rls_policies.py -v`
      green locally against `supabase start`; confirm no test leaves rows.

## Phase 4: RLS module, part B — PR 4 (service_role + storage)

- [ ] 4.1 RED extend `test_rls_policies.py` — add the service_role CRUD test
      (INSERT→UPDATE→DELETE on `products`/`product_variants`/`product_images`
      under `as_role("service_role")`); confirm it fails without `bypassrls`
      present (regression guard on DD1's load-bearing bootstrap detail).
- [ ] 4.2 GREEN — service_role CRUD test passes (proves `BYPASSRLS` + GRANT
      together).
- [ ] 4.3 GREEN — ledger grant-layer test: `service_role` `SELECT`/`INSERT`
      succeed on `stock_movements`; `UPDATE`/`DELETE` raise
      `InsufficientPrivilegeError` (DD5 #1, grant layer only).
- [ ] 4.4 GREEN — append-only trigger test: connect as the table
      **owner/superuser** (not `service_role`); assert `UPDATE`/`DELETE` on
      `stock_movements` raise `asyncpg.exceptions.RaiseError` matching
      `"append-only"` (DD5 #2, trigger layer — precision fix, not reopened).
- [ ] 4.5 GREEN — storage tests: seed two buckets + objects as superuser;
      under `as_role("anon")` reads return only `product-photos` objects,
      `INSERT` denied, `UPDATE`/`DELETE` affect 0 rows; under
      `as_role("service_role")` `INSERT` succeeds.
- [ ] 4.6 Verify: full `test_rls_policies.py` suite green (~14 parametrized
      tests total); confirm CI (Phase 2's workflow) actually runs it (D4).

## Phase 5: Final regression + delivery

- [ ] 5.1 `cd backend && uv run pytest -q` — full suite green, including the
      ~15 previously-skipping DB files, the new safety test, the RLS module.
- [ ] 5.2 `cd frontend && npm run lint && npm test -- --run && npm run build`
      — full frontend suite green with loopback placeholders.
- [ ] 5.3 Confirm zero diff under `supabase/migrations/`, `backend/src/`,
      `frontend/src/` (D5); confirm no `secrets.` token or real Supabase
      value anywhere in the diff (D2).
- [ ] 5.4 Push the assembled branch(es) per the chosen chain strategy and
      confirm the real GitHub Actions run is green end to end — the
      workflow's own verification step (no traditional RED/GREEN for YAML).
