# Delta for platform-foundation

## ADDED Requirements

### Requirement: Automated CI Pipeline Enforces Pinned Quality Gates And RLS Tests

The repository MUST include a CI workflow that automatically executes the
repo's pinned quality gates — backend `ruff check`, backend `pytest`,
frontend `npm run lint`, frontend `npm test`, and frontend `npm run build` —
on the project's configured trigger(s), without requiring a developer to run
them manually. The backend job MUST run its `pytest` suite against a real,
ephemeral Postgres instance with `supabase/migrations/` replayed, so that
database-dependent tests execute for real rather than skipping via the
`DB_URL`-unset short-circuit. The workflow MUST include and execute a
dedicated Row-Level-Security integration test module that exercises, at the
SQL role level, the RLS-related requirements already defined in
`product-catalog-schema`, `inventory-schema`, and `product-media-storage`. A
failing CI run is advisory only in this change; this requirement does not
assert any branch-protection or required-status-check enforcement.

#### Scenario: CI runs both stacks' pinned commands
- GIVEN a push or pull request that triggers the workflow
- WHEN the CI job graph completes
- THEN backend `ruff check`, backend `pytest`, frontend `npm run lint`,
  frontend `npm test`, and frontend `npm run build` MUST all have executed
- AND a failure in any of them MUST be visible on the workflow run

#### Scenario: Backend tests run against a live database, not a skip no-op
- GIVEN the backend CI job
- WHEN the pinned backend test command runs
- THEN `DB_URL` MUST be set to a reachable ephemeral Postgres service with
  `supabase/migrations/` already applied
- AND the `db_pool` fixture MUST NOT skip any database-dependent test

#### Scenario: RLS requirements are exercised by dedicated tests, not prose
- GIVEN the CI-provisioned ephemeral Postgres with migrations replayed
- WHEN the dedicated RLS integration test module runs
- THEN it MUST assert, via `SET ROLE`, that `anon`/`authenticated` are denied
  on the base catalog and inventory tables, can read the public catalog
  views without soft-deleted rows, and that `service_role` has the CRUD
  boundaries and append-only enforcement already required by
  `product-catalog-schema` and `inventory-schema`
- AND it MUST assert the public-read/service-role-write storage policy
  already required by `product-media-storage`
