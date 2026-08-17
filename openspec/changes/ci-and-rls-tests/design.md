# Design: CI Pipeline + RLS Integration Tests

## Technical Approach

Two additive surfaces plus one bootstrap surface the proposal predicted (DD1),
wired so the spec's three scenarios are executable:

1. `.github/workflows/ci.yml` — two **parallel** jobs (DD3). The backend job
   attaches a `postgres:17` service container, applies a repo-owned CI bootstrap,
   replays `supabase/migrations/*.sql` with `psql -v ON_ERROR_STOP=1`, exports
   `DB_URL`, and runs the pinned backend gates. The frontend job runs the pinned
   frontend gates with public-by-design placeholder env vars (D2).
2. `supabase/ci/*.sql` — **not migrations**. Two CI-only scripts that recreate the
   pieces Supabase provisions *outside* `supabase/migrations/`: the three Data API
   roles, and a minimal `storage` schema. Without them, replay dies at the first
   `GRANT ... TO service_role` and again at `create policy ... on storage.objects`.
3. `backend/tests/integration/db/test_rls_policies.py` — SQL-role assertions (D3)
   reusing `db_conn` **unchanged**, with a module-local `as_role()` savepoint
   helper. No new conftest, no fixture change (D5).
4. `backend/tests/architecture/test_ci_workflow_safety.py` — makes D2 executable
   instead of "the reviewer must confirm it" (see Threat Matrix).

No migration, no `backend/src/`, no `frontend/src/` (D5). One documentation-only
line changes in `openspec/config.yaml` (DD2b).

## Architecture Decisions

### DD1: Vanilla `postgres:17` + repo-owned CI bootstrap, not a Supabase-flavored image

**Confirmed from the migrations, not assumed.** All five files were read. Replay
against a bare image fails in **two** places, not one:

| Migration | Missing object on a bare image |
|---|---|
| `20260810000458_public_catalog_rls.sql` | roles `service_role`, `anon`, `authenticated` (4 `GRANT` statements, lines 63–68) |
| `20260810000502_storage_product_photos.sql` | the entire `storage` schema — `storage.buckets` **and** `storage.objects` |

The storage half is the part the proposal did not anticipate: `storage.buckets` /
`storage.objects` are owned by the Supabase **Storage service**, not by any
migration in this repo, so no image choice that lacks a running storage-api is
guaranteed to have them.

| Option | Tradeoff | Decision |
|---|---|---|
| `supabase/postgres:*` image | Would supply the roles, but whether a given tag ships `storage.objects` is an unpinned implementation detail of an image this repo does not otherwise depend on. Large pull; silent drift between tags is exactly the "green CI, false confidence" risk | Rejected |
| Full `supabase start` in CI | Highest fidelity, but explicitly rejected by the proposal's chosen approach; pulls Studio/Auth/Realtime/Kong for a suite that speaks only `asyncpg` | Rejected (out of scope) |
| **`postgres:17` + `supabase/ci/*.sql`** | The stubbed `storage` table *shape* is ours, so its fidelity is an assumption we own and must document | **Chosen** |

Rationale: `postgres:17` matches `config.toml`'s `major_version = 17` exactly, is
tiny and fast (the proposal ranks speed/reliability above breadth), and every
privilege the tests depend on becomes **reviewable text in the diff** rather than
an opaque image layer. The two scripts live under `supabase/ci/` — beside the
existing non-CLI `supabase/tests/` precedent, and unreachable by the CLI, whose
`db.migrations.schema_paths` is `[]` and `db.seed.sql_paths` is `["./seed.sql"]`.

**`service_role` gets `BYPASSRLS`** — load-bearing, and corroborated in-repo:
`20260810000458_public_catalog_rls.sql:61-62` states "service_role only (bypasses
RLS via BYPASSRLS, but still needs an explicit GRANT because nothing is
auto-exposed)". This is what makes the service_role CRUD tests meaningful: the
base tables have RLS enabled with **zero** policies, so a role with full GRANTs
but no `BYPASSRLS` would see 0 rows on `SELECT` and be rejected on `INSERT`. Those
tests therefore prove `BYPASSRLS` as a side effect.

**Documented fidelity gap** (joins the deferred PostgREST gap from D3): the
`storage` stub reproduces Supabase's grant posture — broad table privileges to
`anon`/`authenticated`/`service_role` with RLS doing the restricting. If that
posture is wrong, the anon-read test would pass for the wrong reason (missing
GRANT rather than the policy). The stub grants deliberately, so the test proves
the **policy**.

### DD2a: `ruff format --check` is added, with a binary apply-time precondition

`ruff format` is configured in `backend/pyproject.toml` and has never been
invoked. Whether the tree is already format-clean **cannot be determined by
reading** and this phase has no shell.

**Choice**: include the step in the workflow, and make `sdd-tasks` emit an
explicit gate task: run `uv run ruff format --check` from `backend/` *before*
committing the workflow.
- Exit 0 → keep the step.
- Non-zero → **delete the step** and record a follow-up. Do **not** run
  `uv run ruff format`: it would rewrite `backend/src/**`, which D5 forbids.

**Alternatives**: defer the gate entirely (loses a free, already-configured gate
if the tree is clean); ship it with a "known violations" exception (a red first
CI run sets exactly the wrong convention and D7 makes it un-actionable anyway).
`ruff check` already carries `I` (import order), so the marginal value is
whitespace/quote/wrap consistency — worth having, not worth going red for.

### DD2b: No standalone `tsc --noEmit` step; `next build` stays the type gate

**Evidence, not preference.** `frontend/src/app/layout.tsx:26` uses
`LayoutProps<"/">` — a **Next-generated global type** emitted into `.next/types/`.
`tsconfig.json` includes `.next/types/**/*.ts`, and `frontend/.gitignore` ignores
both `/.next/` and `next-env.d.ts`. On a fresh CI clone neither exists, so a
standalone `tsc --noEmit` run *before* a build fails on `Cannot find name
'LayoutProps'`. Running it *after* `next build` is pure duplication: Next
type-checks the whole project during build and fails on TS errors.

**Choice**: no `typecheck` script, no `tsc` step. Instead, remove the drift by
correcting the one line in `openspec/config.yaml` that names a type checker this
repo does not have:

```yaml
# openspec/config.yaml -> testing.quality_tools
type_checker: "next build --webpack (Next-integrated tsc; no standalone tsc script)"
```

This is the reconciliation the proposal conditioned on DD2 ("Possibly Modified").
`runner_command` and `test_command` are untouched.

### DD3: `push` to `main` + `pull_request` into `main`, two parallel jobs

| Option | Tradeoff | Decision |
|---|---|---|
| Push only | A PR from a branch gets no signal until merge — the worst moment to learn | Rejected |
| PR only | This repo's history commits **directly to `main`** (`4881583`, `391d0c6`, …), so most work would never be checked | Rejected |
| **Both, `push` filtered to `main`** | — | **Chosen** |

Filtering `push` to `branches: [main]` is what prevents double runs: a PR branch
push fires only `pull_request`. `workflow_dispatch` is added for manual re-runs.

**Parallel `backend` + `frontend` jobs, no `needs:`.** Disjoint toolchains
(uv/Python vs npm/Node), zero shared artifacts, and only one of them needs the
Postgres service. Parallel halves wall-clock and — decisive here — keeps the two
signals independent, so an eslint failure cannot hide an RLS failure. A single
sequential job would be simpler to read but would violate the first spec scenario
in spirit ("*all* must have executed").

For the same reason, every **quality-gate** step carries `if: ${{ !cancelled() }}`
so one red gate still lets the rest report. Setup steps (checkout, bootstrap,
install) deliberately do **not**, so a broken environment fails fast.

### DD4: RLS tests reuse `db_conn` as-is; role switching happens inside a SAVEPOINT

**No new conftest fixture.** `db_conn` already gives a superuser connection inside
a rolled-back transaction, which is exactly right: fixture rows are written as
superuser *before* switching role, and the role-switched block sees them because
it is the same transaction.

The non-obvious part is why a plain `SET ROLE` is not enough. A denied statement
**aborts the transaction**, so every later statement in the same test dies with
`InFailedSQLTransactionError` instead of raising its own error. Wrapping each
role-scoped block in a nested `conn.transaction()` (asyncpg emits a SAVEPOINT)
makes the denial recoverable *and* restores `SET LOCAL ROLE` on rollback — the
same mechanism `tests/conftest.py`'s docstring already describes for nested
transactions.

Helper lives **in the module**, not in `conftest.py`: it is useful to exactly one
file, and `conftest.py` is marked Unchanged by the proposal.

### DD5: The append-only proof is two assertions, because service_role never reaches the trigger

The proposal's success criterion — "`UPDATE`/`DELETE` proven blocked by the
append-only trigger despite `BYPASSRLS`" — is **not literally reachable**, and the
migrations say why: `20260810000458_public_catalog_rls.sql:65` grants only
`select, insert` on `stock_movements` to `service_role`. `service_role` is stopped
by the **GRANT layer**, one layer above the trigger. `BYPASSRLS` skips row
security; it does not conjure a missing table privilege.

So the intent is honored by proving the defence in depth explicitly:

1. `service_role` `UPDATE`/`DELETE` → `InsufficientPrivilegeError` (**grant layer**).
2. The **owner/superuser** — which has every privilege *and* bypasses RLS — is
   still rejected by `reject_stock_movements_mutation` with
   `asyncpg.exceptions.RaiseError` matching `append-only` (**trigger layer**).

This is a precision fix to the proposal's wording, not a reopening of D3/D4.
`20260810000453_stock_movements_ledger.sql:39-40` makes the same point ("GRANT
alone does not bind a direct postgres/superuser connection").

## CI Job Flow

    push→main / PR→main / workflow_dispatch
        │
        ├─ job: backend ────────────────────────────────────────────────┐
        │    service postgres:17 (pg_isready health gate)               │
        │    checkout                                                   │
        │    psql -f supabase/ci/00_supabase_roles.sql   ← anon/auth/service_role
        │    psql -f supabase/ci/01_storage_schema.sql   ← storage.buckets/objects
        │    for f in supabase/migrations/*.sql: psql -f "$f"  (lexicographic = timestamp)
        │    setup-uv (3.13) → uv sync --locked
        │    DB_URL=postgresql://postgres:postgres@127.0.0.1:5432/postgres
        │    ruff check → ruff format --check (DD2a) → pytest -q
        │         └─ db_pool NO LONGER SKIPS  →  ~15 dormant DB files + test_rls_policies.py run
        │
        └─ job: frontend ───────────────────────────────────────────────┘
             checkout → setup-node 22 (npm cache) → npm ci
             NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:54321  (placeholder, D2)
             npm run lint → npm test -- --run → npm run build (= type gate, DD2b)

`next build` prerenders `/` and `/catalog` (`revalidate = 300`, no
`generateStaticParams`), so it *attempts* a Supabase read at build time. That is
safe: `catalog-listing-content.tsx:47` handles a failed read as
`emptyStateVariant="error"` — the archived "reads never throw" decision — so the
build succeeds against an unreachable placeholder. `127.0.0.1:54321` is chosen
over a `*.supabase.co` hostname precisely so no DNS leaves the runner and no real
project is ever addressable.

## File Changes

| File | Action | Description |
|---|---|---|
| `.github/workflows/ci.yml` | Create | First CI pipeline. Two parallel jobs, DD3 triggers, `permissions: contents: read` |
| `supabase/ci/00_supabase_roles.sql` | Create | CI-only. `anon`/`authenticated`/`service_role` (+`BYPASSRLS`). **Not a migration** |
| `supabase/ci/01_storage_schema.sql` | Create | CI-only. Minimal `storage.buckets`/`storage.objects` + RLS + Supabase-equivalent grants |
| `backend/tests/integration/db/test_rls_policies.py` | Create | The RLS module (D3/D4). `as_role()` helper + ~14 parametrized tests |
| `backend/tests/architecture/test_ci_workflow_safety.py` | Create | Static guard making D2 executable (no `secrets.`, no `pull_request_target`, no event interpolation in `run:`) |
| `openspec/config.yaml` | Modify | One line: `quality_tools.type_checker` (DD2b) |
| `backend/tests/conftest.py` | **Unchanged** | `DB_URL` skip semantics carry over; CI just sets the var |
| `frontend/package.json` | **Unchanged** | DD2b: no `typecheck` script added |
| `supabase/migrations/**` | **Unchanged** | Read-only replay input. No migration |
| `backend/src/**`, `frontend/src/**` | **Unchanged** | D5 |

## Interfaces / Contracts

### `.github/workflows/ci.yml` (shape sdd-apply must produce)

```yaml
name: CI
on:
  push: { branches: [main] }
  pull_request: { branches: [main] }
  workflow_dispatch:
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
permissions:
  contents: read

jobs:
  backend:
    name: Backend (ruff + pytest on ephemeral Postgres)
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17
        env: { POSTGRES_USER: postgres, POSTGRES_PASSWORD: postgres, POSTGRES_DB: postgres }
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready --health-interval 10s
          --health-timeout 5s --health-retries 10
    env:
      DB_URL: postgresql://postgres:postgres@127.0.0.1:5432/postgres
    steps:
      - uses: actions/checkout@v4
      - name: Bootstrap Supabase-managed roles and storage surface
        run: |
          psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/ci/00_supabase_roles.sql
          psql "$DB_URL" -v ON_ERROR_STOP=1 -f supabase/ci/01_storage_schema.sql
      - name: Replay supabase/migrations
        run: |
          for f in supabase/migrations/*.sql; do
            echo "-- applying $f"
            psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f"
          done
      - uses: astral-sh/setup-uv@v5
        with:
          python-version: "3.13"
          enable-cache: true
          cache-dependency-glob: backend/uv.lock
      - run: uv sync --locked
        working-directory: backend
      - { name: ruff check,        if: ${{ !cancelled() }}, working-directory: backend, run: uv run ruff check }
      - { name: ruff format,       if: ${{ !cancelled() }}, working-directory: backend, run: uv run ruff format --check }
      - { name: pytest,            if: ${{ !cancelled() }}, working-directory: backend, run: uv run pytest -q }

  frontend:
    name: Frontend (lint + vitest + build)
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: frontend } }
    env:
      NEXT_PUBLIC_SUPABASE_URL: http://127.0.0.1:54321
      NEXT_PUBLIC_SUPABASE_ANON_KEY: ci-placeholder-anon-key
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 22, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - run: npm ci
      - { name: eslint,     if: ${{ !cancelled() }}, run: npm run lint }
      - { name: vitest,     if: ${{ !cancelled() }}, run: npm test -- --run }
      - { name: next build, if: ${{ !cancelled() }}, run: npm run build }
```

Notes for apply: `working-directory: backend` reproduces the pinned commands from
`openspec/config.yaml` exactly (`uv run --project backend pytest -q` ≡ `uv run
pytest -q` with cwd `backend`), and keeps `ruff`'s `src = ["src", "tests"]`
resolution correct — running ruff from the repo root would not. `psql` is
preinstalled on `ubuntu-latest`; if a future image drops it, prepend
`sudo apt-get install -y postgresql-client` rather than changing the DSN.
D6 pins `npm test -- --run`; the script is already `vitest run`, so the trailing
flag is redundant — drop it **only** if vitest rejects it, never as a preference.

### `supabase/ci/00_supabase_roles.sql`

```sql
-- CI ONLY. NOT a migration. Never applied to a real Supabase project.
-- Recreates the three Data API roles Supabase provisions outside
-- supabase/migrations/, so replay's GRANT statements resolve.
create role anon           nologin noinherit;
create role authenticated  nologin noinherit;
-- BYPASSRLS is load-bearing: the base tables have RLS enabled with zero
-- policies, so without it every service_role assertion would invert.
create role service_role    nologin noinherit bypassrls;

grant usage on schema public to anon, authenticated, service_role;
```

### `supabase/ci/01_storage_schema.sql`

```sql
-- CI ONLY. Minimal stand-in for the `storage` schema owned by the Supabase
-- Storage service. Only what 20260810000502_storage_product_photos.sql and
-- test_rls_policies.py actually touch is reproduced.
create schema if not exists storage;

create table storage.buckets (
  id text primary key,
  name text not null,
  public boolean not null default false,
  created_at timestamptz not null default now()
);

create table storage.objects (
  id uuid primary key default gen_random_uuid(),
  bucket_id text references storage.buckets (id),
  name text,
  owner uuid,
  metadata jsonb,
  created_at timestamptz not null default now(),
  last_accessed_at timestamptz not null default now()
);

alter table storage.buckets enable row level security;
alter table storage.objects enable row level security;

-- Supabase grants table privileges broadly here and lets RLS restrict.
-- Reproduced so the anon-read test proves the POLICY, not a missing GRANT.
grant usage on schema storage to anon, authenticated, service_role;
grant select on storage.buckets to anon, authenticated;
grant all    on storage.buckets to service_role;
grant all    on storage.objects to anon, authenticated, service_role;
```

### `test_rls_policies.py` — role-switch helper (the one non-obvious pattern)

```python
BASE_TABLES = ("products", "product_variants", "product_images", "stock_movements")
CATALOG_VIEWS = ("catalog_products", "catalog_variants", "catalog_product_images")
RESTRICTED_ROLES = ("anon", "authenticated")


@asynccontextmanager
async def as_role(conn: asyncpg.Connection, role: str) -> AsyncIterator[asyncpg.Connection]:
    """Run a block as `role` inside a SAVEPOINT.

    Two reasons for the savepoint, both mandatory:
    1. A denied statement aborts the transaction; without it every later
       statement raises InFailedSQLTransactionError instead of its own error.
    2. Rolling back restores `SET LOCAL ROLE`, returning the caller to the
       superuser `db_conn` connected as.
    `role` is always a literal from the constants above -- never test input --
    so the quoted-identifier f-string carries no injection surface.
    """
    savepoint = conn.transaction()
    await savepoint.start()
    await conn.execute(f'SET LOCAL ROLE "{role}"')
    try:
        yield conn
    finally:
        await savepoint.rollback()
```

Expected exception mapping (asserted, not incidental):

| Situation | Raised |
|---|---|
| No table privilege at all (`anon` on base tables; `service_role` UPDATE on `stock_movements`) | `asyncpg.exceptions.InsufficientPrivilegeError` |
| RLS enabled, no INSERT policy (`anon` into `storage.objects`) | `InsufficientPrivilegeError` (SQLSTATE 42501) |
| RLS enabled, no SELECT/UPDATE policy | **no error** — 0 rows / `UPDATE 0` command tag |
| Append-only trigger | `asyncpg.exceptions.RaiseError`, message matches `append-only` |

## Testing Strategy

| Layer | What to test | Approach |
|---|---|---|
| Integration (RLS, denial) | `anon` + `authenticated` `SELECT` denied on all 4 base tables | `as_role` + `pytest.raises(InsufficientPrivilegeError)`, parametrized 2×4 |
| Integration (RLS, privilege matrix) | Zero `SELECT/INSERT/UPDATE/DELETE` for both roles on all 4 base tables | `SELECT has_table_privilege($1,$2,$3)` is `False`, parametrized 2×4×4 — exact, and no `SET ROLE` needed |
| Integration (RLS, views) | Both roles read all 3 catalog views for a seeded product | `as_role` + `count(*) == 1` per view |
| Integration (RLS, soft delete) | Retiring the product hides it from all 3 views **for `anon`**; retiring one variant hides only that variant + its image; a live sibling stays visible | Seed as superuser → `UPDATE ... SET deleted_at = now()` → assert under `as_role` |
| Integration (RLS, internal view) | `variant_stock_levels` is **not** readable by `anon`/`authenticated` | privilege check + behavioral denial |
| Integration (service_role CRUD) | INSERT → UPDATE → DELETE succeed on `products`/`product_variants`/`product_images` | `as_role("service_role")`; succeeds only because of `BYPASSRLS` + GRANT, so this doubles as the `BYPASSRLS` proof |
| Integration (service_role ledger) | `SELECT`/`INSERT` on `stock_movements` succeed; `UPDATE`/`DELETE` raise `InsufficientPrivilegeError` | Grant-layer assertion (DD5 #1) |
| Integration (append-only trigger) | Owner/superuser `UPDATE`/`DELETE` still rejected | `pytest.raises(RaiseError, match="append-only")` (DD5 #2) |
| Integration (storage) | `anon` sees only `product-photos` objects, not a second bucket's; `anon` INSERT denied; `anon` UPDATE/DELETE affect 0 rows; `service_role` INSERT succeeds | Seed two buckets + objects as superuser, assert under `as_role` |
| Architecture (static) | No `${{ secrets.` anywhere in `.github/workflows/`; no `pull_request_target`; no `${{ github.event.*` inside a `run:` block; `permissions:` declared; the placeholder Supabase URL is loopback | New `test_ci_workflow_safety.py`, same static-grep pattern as the existing `test_frontend_service_role_boundary.py` |
| Pipeline (self-proving) | `db_pool` does not skip in CI | Replay + `DB_URL` are prerequisites of the job; a skip shows as `s` in `pytest -q` output |
| E2E | N/A | No PostgREST/HTTP-level RLS coverage — deferred by D3, documented residual gap |

**Ordering for apply (proposal's own "prove replay first" advice):** bootstrap +
replay must be proven green **before** any assertion is written. Every RLS
assertion is worthless if `psql` never got past `20260810000502`.

## Threat Matrix

| Boundary | Applicability | Design response | Planned RED test |
|---|---|---|---|
| Documentation-like paths | **N/A** — no file classification or executable-content decision | — | — |
| Git repository selection | **N/A** — `actions/checkout` only; no `git -C`, no user-supplied path | — | — |
| Commit state | **N/A** — CI never stages or commits | — | — |
| Push state | **N/A** — `permissions: contents: read`; no push, tag, or release step | — | — |
| PR commands | **N/A** — no `gh pr` automation | — | — |
| **Shell / subprocess (workflow `run:` blocks)** | **Applicable** — this change introduces the repo's first CI shell execution | No `${{ github.event.* }}` / `github.head_ref` interpolation inside any `run:`; every value is a literal or job-level `env`. `pull_request`, never `pull_request_target`, so fork PRs get a read-only token and no secret context. `permissions` declared explicitly | `test_ci_workflow_safety.py`: asserts no `${{ github.event`/`github.head_ref` inside `run:`, no `pull_request_target`, `permissions:` present |
| **Secret exposure (D2)** | **Applicable** — highest-severity risk in the proposal | Zero GitHub Secrets. Postgres credentials are container-local; `NEXT_PUBLIC_*` are loopback placeholders | `test_ci_workflow_safety.py`: asserts no `${{ secrets.` token, and that the Supabase URL is loopback (not `*.supabase.co`) |
| **SQL role interpolation** | **Applicable** — `SET LOCAL ROLE "{role}"` is an f-string | Role names come only from module-level literal tuples, quoted as identifiers; no parameter, fixture, or env value ever reaches it | Enforced by construction; the parametrize ids are the literals themselves |

## Migration / Rollout

**No migration.** No schema, policy, grant, index, or dependency change; `supabase/ci/*.sql`
runs only against a throwaway container and is invisible to the Supabase CLI.

Rollout is inherently safe: the workflow is **advisory only** (D7), no branch
protection or required check is configured, and nothing in the runtime path is
touched. Rollback = delete `.github/workflows/ci.yml` (CI only) or revert the
commit (everything); the RLS module then remains runnable locally with `DB_URL`.

**Named rollout risk:** ~15 DB-dependent test files that have silently skipped
since inception execute for the first time in CI. They are green locally against
`supabase start`, but the CI database has no seed data and no auth/storage
services. First-run failures there are **pre-existing latent defects surfaced by
this change, not caused by it**; treat them as follow-ups unless trivially fixable
without touching `backend/src/` (D5).

## Open Questions

None blocking. `storage.objects`' read policy is `to anon` only —
`authenticated` cannot read product photos at the SQL level. The bucket is
`public = true`, so the Storage HTTP API serves it regardless, which is
probably why nobody noticed. **Resolved by the user on 2026-08-17**: the RLS
test asserts today's actual behavior (no `authenticated` policy), and a
**separate follow-up SDD change** (with its own migration) is tracked to add
an `authenticated` read policy — out of scope here since D5 forbids any
migration in this change.
- [ ] **DD2a's outcome** is resolved at apply time by running
      `uv run ruff format --check`. Binary, procedure defined above; no further
      decision needed from anyone.
- [ ] **Stub-vs-real `storage` fidelity** (DD1) — revisit only if a real
      divergence is observed. The upgrade path is `supabase start` in CI, already
      scoped out by the proposal.
