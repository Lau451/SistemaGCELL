# Proposal: CI Pipeline + RLS Integration Tests

## Intent

This repo has **no CI at all** — no `.github/workflows/`, no other CI config
anywhere. Every quality gate (`ruff check`, `pytest`, `npm run lint`,
`npm test`, `npm run build`) is run manually, by memory, by one developer.

Worse, the gates that *are* pinned silently no-op: `backend/tests/conftest.py`'s
`db_pool` fixture calls `pytest.skip(...)` when `DB_URL` is unset, so ~15+ DB
integration test files pass vacuously on any machine without a live Postgres.

Meanwhile the database's **security boundary has zero executable coverage**.
`product-catalog-schema`, `inventory-schema`, and `product-media-storage` all
carry *merged, shipped* RLS requirements (anon denied on base tables,
`service_role` unrestricted, storage read-public/write-restricted) that **no
test has ever executed**. The one role-boundary test that exists
(`tests/architecture/test_frontend_service_role_boundary.py`) is a static grep
for the literal string `SERVICE_ROLE` in frontend source — it proves the
frontend never *names* the key, and proves nothing about Postgres enforcement.
The existing `DB_URL` connects as the Postgres **superuser**, which bypasses RLS
entirely, which is exactly why no existing test could have caught a regression.

These two gaps are one problem: RLS tests written without CI would just repeat
the "written once, never run automatically" pattern that *is* the gap.

## Scope

### In Scope

- **First GitHub Actions workflow** (`.github/workflows/`), running the gates
  that already exist: backend `ruff check`, backend `pytest` (against an
  ephemeral Postgres service container with `supabase/migrations/` replayed),
  frontend `npm run lint`, frontend `npm test -- --run`, frontend `npm run
  build` (which fails on TS errors, so it doubles as the typecheck gate — this
  repo has **no** separate typecheck script).
- **New RLS test module** (`backend/tests/integration/db/test_rls_policies.py`),
  reusing the existing `db_pool` / `db_conn` fixture conventions, covering:
  - `anon` and `authenticated` denied on all 4 base tables (`products`,
    `product_variants`, `product_images`, `stock_movements`) — currently
    *double*-denied: zero policies **and** zero grants.
  - `anon` / `authenticated` **can** read the 3 public catalog views
    (`catalog_products`, `catalog_variants`, `catalog_product_images`) but
    **cannot** see soft-deleted rows (the `WHERE deleted_at IS NULL` filter
    added by the soft-delete migration — currently untested).
  - `service_role` full CRUD on `products` / `product_variants` /
    `product_images`, but only `SELECT` + `INSERT` on `stock_movements`.
  - The **append-only trigger still blocks `service_role` UPDATE/DELETE** on
    `stock_movements` even though `BYPASSRLS` skips row security — an untested
    interaction between RLS bypass and a trigger-level constraint.
  - `storage.objects`' single existing policy: public `SELECT` for `anon`,
    scoped to the `product-photos` bucket only.
- CI wired so the **new** RLS tests actually run, not just the pre-existing ones.

### Out of Scope

| Deferred | Rationale |
|---|---|
| **PostgREST / HTTP-level RLS tests** with real anon/service_role API keys | Explicitly deferred (D3). Would require the full Supabase stack in CI. Documented as a known residual gap, not a defect. |
| **Any real Supabase credentials / GitHub Secrets** | D2. Nothing in this change touches the real project. |
| **Any Supabase migration / schema / policy / grant change** | **No migration.** Policies and grants already exist from prior migrations; this change only *tests* them. |
| Application, domain, or API code | **Zero.** No `backend/src/`, no `frontend/src/` (beyond CI reading them). |
| Deploy / release / publish automation | This is a *verification* pipeline only. |
| Branch-protection rules, required-check enforcement | See OQ1 — a repo-settings decision, not a file in this diff. |
| Coverage reporting, matrix builds, caching tuning | Prioritize a fast, reliable first gate over breadth (see Risks). |
| Any Gemini API usage | **None introduced.** |

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None.

**This is infra/quality work with no capability delta.** It changes no
product behavior and no requirement text. Its value is that it makes
*already-merged* requirements executable for the first time — the RLS
scenarios in `product-catalog-schema` (anon denied on base tables, anon reads
via view, service_role unrestricted), `inventory-schema` (anon denied on
`stock_movements`, service_role reads all movements, append-only), and
`product-media-storage` (public read, service_role-only write) become real
assertions instead of prose.

`sdd-spec` MUST decide explicitly (see OQ1) whether this change is legitimately
**spec-less** — the first such change this session — or whether the CI gate
warrants one ADDED requirement under `platform-foundation`, which already hosts
comparable repo-level requirements ("Pinned Testing Configuration Unblocks
Strict TDD", "Fresh Clone Reproducibility"). Do not silently create a spec, and
do not silently skip one.

## Approach

Exploration **CI Approach 1** (Postgres service container + migration replay,
*not* full `supabase start`) combined with **RLS Approach 3** (SQL-role-switch
tests now, PostgREST-level tests documented as deferred).

RLS assertions use `SET ROLE anon` / `SET ROLE authenticated` /
`SET ROLE service_role` on a connection to a real ephemeral Postgres with all
5 migration files replayed, reusing the established `db_pool`/`db_conn`
fixtures rather than inventing new test infrastructure.

### Locked Decisions

| # | Decision |
|---|----------|
| D1 | **One bundled change**, named `ci-and-rls-tests` — no `admin-` prefix. Repo-wide infra/quality, not admin-panel product scope. Splitting into two SDD changes is rejected: RLS tests without CI reproduce the exact gap. |
| D2 | **No real secrets, none.** CI uses only an ephemeral, workflow-local Postgres service container plus safe placeholder values (dummy `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` for `next build`, since `next.config.ts` → `getCatalogSupabaseEnv()` throws when they are unset, the anon key is public-by-design, and the build makes no network call). **Never connects to the real Supabase project. Zero GitHub Secrets for this scope.** |
| D3 | **RLS test scope is SQL-level only** — `SET ROLE` against real ephemeral Postgres with migrations replayed, reusing `db_pool`/`db_conn`. **Not** PostgREST-level HTTP tests; those are explicitly deferred, not part of this change. |
| D4 | CI MUST actually execute the **new** RLS tests. A pipeline that only runs pre-existing tests does not close the gap. |
| D5 | **No application code, no domain layer, no API route, no migration.** The diff is new test files plus new CI YAML. Hexagonal boundaries are untouched because no `src/` file is touched. |
| D6 | The pipeline wires the **commands that already exist today**: `ruff check`, `uv run pytest`, `npm run lint`, `npm test -- --run`, `npm run build`. Adding *new* gates is a design decision (DD2), not a locked one. |
| D7 | **A red CI check is advisory only in this change.** No branch-protection or required-status-check enforcement is configured — that is a GitHub repo *setting*, outside this diff, and can be turned on later without touching the workflow file. |

D2–D3, D7 confirmed by the user on 2026-08-17 via AskUserQuestion (D7 = OQ2).
D1, D4–D6 follow from exploration's recommendation plus repo conventions.
**D1–D7 must not be reopened** by `sdd-spec`, `sdd-design`, or `sdd-tasks`.

### Deferred to Design — must be decided **explicitly**, not silently picked

| # | Decision `sdd-design` owns |
|---|---|
| DD1 | **Postgres image flavor + role bootstrap.** A vanilla `postgres:17` image almost certainly does **not** ship Supabase's `anon` / `authenticated` / `service_role` roles, and the migrations `GRANT` to them — so a bare image likely fails at migration replay, not just at test time. Design MUST research and choose: a bootstrap SQL script creating the roles (including `service_role`'s `BYPASSRLS`, without which D3's tests assert the wrong thing), a Supabase-flavored Postgres image, or another mechanism. Genuinely unresolved. |
| DD2 | **Whether to add NEW gates** beyond D6: `ruff format --check` (configured in `pyproject.toml`, never invoked anywhere today) and/or a frontend typecheck step (`tsc --noEmit`; `typescript` is a devDependency but there is **no** script — `openspec/config.yaml` names `tsc --noEmit` as the type checker, so config and `package.json` disagree). Adding either will likely surface pre-existing violations on the first run — design must decide whether that noise belongs in this change. |
| DD3 | **Trigger conditions and job topology** — every push, PRs only, or both; backend and frontend jobs parallel or sequential. First-ever workflow, so whatever is chosen becomes the repo convention. |

### Supabase / Gemini Impact (per `openspec/config.yaml` rules)

- **Supabase schema/migration impact: none.** `supabase/migrations/*.sql` is
  read-only reference input for CI's replay step. No new migration, no policy
  change, no grant change.
- **Gemini API usage: none introduced.**

## Open Questions

| # | Question | Status |
|---|---|---|
| OQ1 | **Is this change legitimately spec-less?** No requirement text changes (Capabilities = None/None), but `platform-foundation` already hosts repo-level infra requirements. Options: (a) no spec file at all — first spec-less change this session; (b) one ADDED requirement under `platform-foundation` asserting an automated CI gate exists and runs both stacks. | Left to `sdd-spec` to decide explicitly (technical/documentation-completeness call, not a product fork) — must state its reasoning, not silently pick. |
| OQ2 | Is a red CI check advisory or blocking? | **Resolved, locked as D7** — advisory only in this change. |

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `.github/workflows/*.yml` | **New** | First CI pipeline in the repo. Does not exist today. |
| `backend/tests/integration/db/test_rls_policies.py` | **New** | The RLS test module (D3). |
| CI role-bootstrap asset (path TBD, DD1) | **New (probable)** | Bootstrap SQL / image choice for `anon`/`authenticated`/`service_role`. |
| `backend/tests/conftest.py` | **Unchanged** | `DB_URL` skip semantics carry over as-is; CI just sets the env var. |
| `supabase/migrations/` | **Unchanged** | **No migration.** Read-only input to CI's replay step. |
| `backend/src/`, `frontend/src/` | **Unchanged** | No application, domain, or API change (D5). |
| `openspec/config.yaml` | Possibly Modified | Only if DD2 resolves toward reconciling the `tsc --noEmit` / no-script mismatch. |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Real credentials leak into a workflow file — the classic first-CI failure | **Low, but highest severity** | D2 is absolute: ephemeral container + public-by-design placeholders only, zero GitHub Secrets. Reviewer must confirm no real value appears in the diff. |
| Role bootstrap (DD1) fails and blocks the whole change — migrations `GRANT` to roles a bare image lacks | **High** | DD1 is a named, mandatory design decision, not an implementation detail. Consider proving migration replay before writing test assertions. |
| A slow or flaky DB-backed job becomes a permanently-red, ignored check | Medium | Prioritize speed/reliability over coverage breadth; keep the RLS module tight and deterministic. |
| RLS tests pass against a CI-only role setup that diverges from real Supabase — green CI, false confidence | Medium | DD1 must favor fidelity to the real role definitions (esp. `service_role` `BYPASSRLS`); PostgREST-level gap stays documented (D3). |
| First-ever GitHub Actions conventions get copied by every future change | Medium (certain, if unaddressed) | DD3 forces trigger/topology to be an explicit decision rather than an accident. |
| Bundled scope overruns the 1200-line review budget | Medium | See Delivery Forecast — `sdd-tasks` produces the real number. |

## Rollback Plan

Cleanest rollback in the session: **delete two new files**. The change is
purely additive and touches no runtime code path, no schema, no migration, and
no production configuration. Reverting the commit removes the workflow and the
test module; every existing test, endpoint, and page behaves exactly as before,
because none of them were modified. If only CI is problematic (flaky, slow),
the workflow file can be deleted or disabled independently of the RLS tests,
which then remain runnable locally via `DB_URL`.

## Dependencies

- `supabase-schema` (archived 2026-08-09) and the soft-delete migration —
  supply the policies, grants, views, and append-only trigger under test.
  Shipped; nothing blocking.
- `platform-foundation` — supplies the pinned test commands CI invokes.
- No external service, account, or credential is required (D2).
- OQ1 is `sdd-spec`'s to answer explicitly when it runs.

## Delivery Forecast

**Medium**, with real chaining risk. Two independent new surfaces (CI YAML,
RLS test module) plus a probable third (DD1 role bootstrap). Review budget for
this session is **1200 lines**, so a single PR is plausible — but a full RLS
matrix (3 roles × 4 tables × 3 views × soft-delete × storage × append-only
trigger) can grow fast, and CI YAML is verbose.

`sdd-tasks` MUST produce a genuine forecast rather than assume either shape. If
chaining is warranted, the natural slices are: (1) CI skeleton with lint / unit
/ build only, (2) Postgres service container + role bootstrap, wiring the
*existing* DB tests in, (3) the new RLS test module. Each slice is independently
green and independently revertable. Do not pre-commit to a chain here.

## Success Criteria

- [ ] A GitHub Actions workflow exists and runs on the agreed triggers (DD3),
      executing backend lint, backend tests, frontend lint, frontend tests, and
      frontend build — advisory only, no branch-protection/required-check
      enforcement is configured in this change (D7).
- [ ] The backend job runs against a real ephemeral Postgres with all
      `supabase/migrations/` replayed — `db_pool` **does not** skip in CI.
- [ ] The new RLS tests run **in CI**, not only locally (D4).
- [ ] `anon` and `authenticated` are proven denied on all 4 base tables, and
      proven able to read the 3 catalog views **without** seeing soft-deleted
      rows.
- [ ] `service_role` is proven to have full CRUD on the 3 product tables, and
      `SELECT`/`INSERT` only on `stock_movements` — with `UPDATE`/`DELETE`
      proven blocked by the append-only trigger despite `BYPASSRLS`.
- [ ] `storage.objects` public-`SELECT`-for-`anon`-on-`product-photos` is
      asserted.
- [ ] No real Supabase credential, service-role key, or GitHub Secret appears
      anywhere in the diff (D2).
- [ ] `supabase/migrations/`, `backend/src/`, and `frontend/src/` are
      **unchanged**; every existing test still passes.
