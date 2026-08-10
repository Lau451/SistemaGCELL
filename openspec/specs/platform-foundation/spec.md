# Delta for platform-foundation

## ADDED Requirements

### Requirement: Frontend Scaffold Boots and Tests Pass
The frontend `Next.js App Router + TypeScript + Tailwind + shadcn/ui + Serwist` scaffold MUST run and MUST have a pinned test command that passes.

#### Scenario: Fresh install, pinned test command
- GIVEN a fresh clone of `frontend/`
- WHEN a developer installs dependencies and runs the pinned frontend test command
- THEN the example Vitest/React Testing Library test MUST pass with exit code 0

#### Scenario: Dev server boots
- GIVEN the frontend scaffold with dependencies installed
- WHEN the developer starts the Next.js dev server
- THEN the app SHALL boot without runtime errors

### Requirement: Backend Scaffold Boots and Tests Pass
The backend `uv`-managed FastAPI hexagonal skeleton MUST run and MUST have a pinned test command that passes.

#### Scenario: Fresh install, pinned test command
- GIVEN a fresh clone of `backend/`
- WHEN a developer syncs dependencies via `uv` and runs the pinned backend test command
- THEN the `products` domain pure-domain unit test AND the `/health` integration test (via `TestClient`) MUST both pass

#### Scenario: Health endpoint responds
- GIVEN the FastAPI app is running
- WHEN a client requests `GET /health`
- THEN the response SHALL return a successful status confirming the service is up

### Requirement: Hexagonal Domain Boundary Enforcement
Each of the 6 backend domains (`products`, `stock`, `content`, `ai`, `recommendation`, `shared`) MUST expose `domain/`, `application/`, `infrastructure/` layers, and the `domain/` layer of every domain MUST NOT import FastAPI, Pydantic, or any DB client library.

#### Scenario: Products domain proves the boundary
- GIVEN the `products` domain's `domain/` layer source files
- WHEN their imports are inspected
- THEN none SHALL reference `fastapi`, `pydantic`, or a database client package

#### Scenario: Skeleton exists for all six domains
- GIVEN the backend scaffold
- WHEN the domain directory tree is listed
- THEN all 6 domains MUST each contain `domain/`, `application/`, and `infrastructure/` subdirectories, even if only `products` has worked implementation logic

### Requirement: Supabase CLI Wiring Without Schema
The repository MUST include `supabase init` wiring, and `supabase/migrations/`
MUST contain the real product-catalog, inventory, RLS, and storage schema
authored by the `supabase-schema` change, applied dependency-first via
CLI-generated migration files.
(Previously: asserted `migrations/` MUST contain no schema SQL files at all —
that constraint is superseded now that the catalog/inventory/storage schema
exists.)

#### Scenario: Config exists, migrations contain real schema
- GIVEN the `supabase/` directory after this change
- WHEN `supabase/config.toml` and `supabase/migrations/` are inspected
- THEN `config.toml` MUST exist AND `migrations/` MUST contain the
  CLI-generated catalog, inventory, RLS, and storage migration files

#### Scenario: Fresh database reset applies all schema cleanly
- GIVEN an empty local Supabase database
- WHEN `supabase db reset` runs
- THEN all migrations MUST apply in dependency order with no errors, leaving
  `products`, `product_variants`, `product_images`, `stock_movements`, their
  public views, and the product-photos bucket in place

### Requirement: Pinned Testing Configuration Unblocks Strict TDD
`openspec/config.yaml` `testing:` block MUST be populated with both frontend and backend commands set to non-null values, and `testing.status` MUST no longer read `not-yet-implemented`.

#### Scenario: Config commands are non-null
- GIVEN `openspec/config.yaml` after this change
- WHEN the `testing:` block is read
- THEN `testing.status` MUST NOT equal `not-yet-implemented` AND both the frontend and backend test commands MUST be non-null strings

### Requirement: PWA Runtime-Caching Strategy Decision
The Serwist PWA configuration MUST document a concrete runtime-caching strategy for public catalog routes, and every real catalog route created by the application MUST conform to that documented strategy's matcher patterns in `frontend/src/lib/pwa/runtime-caching.ts`.
(Previously: allowed the strategy to be documented in advance with no real catalog route required to exist yet.)

#### Scenario: Strategy remains documented
- GIVEN the Serwist configuration files
- WHEN the caching strategy for public catalog routes/images is inspected
- THEN a named strategy per asset class (NetworkFirst for pages, StaleWhileRevalidate for API, CacheFirst for storage images) MUST be documented in `runtime-caching.ts`

#### Scenario: Real catalog routes conform to the pinned matcher
- GIVEN the `public-catalog-ui` and `catalog-search-api` capabilities have introduced real routes (`/`, `/catalog`, `/product/*`, `/api/catalog/*`)
- WHEN each route's path is tested against the corresponding matcher in `runtime-caching.ts`
- THEN every route MUST match its intended matcher
- AND `runtime-caching.ts` itself MUST remain unmodified by the change that introduced those routes

### Requirement: Fresh Clone Reproducibility
A fresh clone MUST reach both green test runs using only documented setup steps, and no ignored build artifact MUST be tracked in git.

#### Scenario: Both stacks pass from a clean clone
- GIVEN a fresh clone with no prior install state
- WHEN a developer follows only the documented setup steps for both `frontend/` and `backend/`
- THEN both pinned test commands MUST complete successfully

#### Scenario: No build artifacts tracked
- GIVEN the repository's tracked file list
- WHEN it is inspected for `node_modules/`, `.next/`, `.venv/`, `__pycache__/`, `supabase/.temp/`
- THEN none of these paths SHALL be tracked in git
