# Exploration: Bootstrap initial repo scaffolding for SistemaGCELL

Frontend + backend + test runners + Supabase wiring.

## Current State

Verified directly against the working directory:

- No application code exists. Only agent tooling is committed: `.claude/`, `.agents/`, `.codex/`, `skills-lock.json`, `.atl/`, `.gitignore`, and a freshly bootstrapped `openspec/` (config.yaml + empty specs/changes trees).
- No `package.json` anywhere in the repo, no `pyproject.toml`, no `frontend/`, `backend/`, `apps/`, `src/`, `web/`, `api/` directories (all glob-checked, zero matches).
- No `supabase/` directory exists — the `supabase/migrations/0001-0004*.sql` files designed in the earlier architecture conversation were never written to disk; they only exist as a discussed plan. `supabase init` has not been run.
- `openspec/config.yaml` already encodes the decided stack (Next.js App Router/TS/Tailwind/shadcn/PWA, FastAPI hexagonal by domain: products/stock/content/ai/recommendation/shared, Supabase São Paulo, Vercel+Fly.io hosting) and flags `testing.status: not-yet-implemented`, all runner/command fields `null` — the first `sdd-tasks` phase must pin frontend+backend test commands before task breakdown (Strict TDD Mode).

## Affected Areas (will be created by this change, none exist yet)

- `frontend/` — new Next.js App Router project (route groups `(public)` and `(admin)`)
- `backend/` — new FastAPI project, hexagonal folders per domain
- `supabase/` — new, via `supabase init` (config.toml, migrations/, seed.sql) — folder wiring only, NOT the actual schema SQL
- `openspec/config.yaml` `testing:` block — needs `runner_command`/`frameworks`/`layers`/`coverage` filled once commands are pinned (done in `sdd-tasks`, not here)
- Root `.gitignore` — needs entries for `node_modules/`, `.next/`, `.venv/`, `__pycache__/`, `supabase/.temp/`, etc.

## Approaches

### 1. Frontend scaffolding tool

`create-next-app@latest --ts --tailwind --eslint --app` + `npx shadcn@latest init` + Serwist for PWA (`@serwist/next`, `@serwist/sw`) — Serwist is the actively maintained successor to `next-pwa`, which is unmaintained.

- Pros: official/current tooling, matches Next.js + TS + Tailwind + shadcn in one command chain, PWA service worker is TypeScript-native and App-Router-aware.
- Cons: PWA wiring (manifest.json, icons, service worker registration) still needs manual steps after install; Tailwind v4's zero-config mode changes fast, must pin exact versions.
- Effort: Low

### 2. Backend scaffolding — Python dependency manager

**uv** (Astral) vs Poetry vs pip-tools.

- uv: single Rust binary replacing pyenv+pip+pip-tools+virtualenv+Poetry; much faster installs; `uv init`, `uv add fastapi 'uvicorn[standard]'`, `uv add --dev pytest pytest-asyncio httpx ruff mypy`; produces `pyproject.toml` + `uv.lock`.
- Poetry: mature, plugin ecosystem, slower resolver.
- **Recommendation: uv** — faster local verification loop (this change is explicitly CI-less), single tool reduces onboarding friction.
- Effort: Low

### 3. Backend hexagonal folder layout

Per domain (`products`, `stock`, `content`, `ai`, `recommendation`, `shared`): `domain/` (entities, value objects, repository interfaces — zero framework imports), `application/` (use cases orchestrating domain), `infrastructure/` (FastAPI routers, Supabase client adapters, repository implementations). Domain layer must not import FastAPI/Pydantic/DB clients directly.

- Effort: Low (skeleton only — empty domains + one worked example, `products`)

### 4. Test runner pairing

- **Frontend**: Vitest (unit/component, via `@testing-library/react` + jsdom) + Playwright (e2e). Vitest is now the Next.js team's own tutorial default (native ESM, faster startup than Jest). Playwright is the current e2e leader.
- **Backend**: pytest + `pytest-asyncio` + `httpx.AsyncClient`/`TestClient`. Convention: `backend/tests/unit/<domain>/` (pure domain/application logic) vs `backend/tests/integration/api/` (endpoint tests via TestClient).
- Effort: Low–Medium. Playwright adds a second install + browser binaries — **recommend deferring Playwright to a later change** since there's no real UI flow yet to test, keeping this change's pinned command surface smaller.

### 5. Supabase local wiring

`supabase init` creates `supabase/config.toml`, `supabase/migrations/`, `supabase/seed.sql`. `supabase start` boots local Postgres+Storage via Docker (Docker Desktop required — not yet confirmed installed on this machine). `supabase migration new <name>` generates a **timestamp-prefixed** filename (e.g. `20260808120000_initial_schema.sql`) — this does **not** match the `0001-0004` naming used in the earlier design conversation, a naming-convention mismatch that must be reconciled before any real schema SQL is authored.

- Recommendation for this change: run `supabase init` only, to wire folder structure and `.gitignore`; do not author the actual 4 schema migration files yet — that needs `sdd-spec` first.
- Effort: Low (init only) / Medium-High if actual schema SQL is included (out of scope here)

## Recommendation

Scope `initial-scaffolding` as a bare-bones, CI-less, locally-verifiable skeleton:

**In scope:**
- `frontend/`: `create-next-app` (TS, Tailwind, App Router, ESLint) + `shadcn@latest init` + Serwist PWA skeleton (manifest + minimal service worker) + Vitest/RTL with one passing example test (pinned command). Playwright deferred.
- `backend/`: uv-managed FastAPI skeleton with the 6 hexagonal domain folders (stubs), one worked example domain (`products`) with a passing pure-domain unit test and a passing `/health` integration test via TestClient (pinned command).
- `supabase/`: `supabase init` only — folder + config.toml wiring, no schema SQL yet.
- `openspec/config.yaml` `testing:` block updated with the pinned commands — this unblocks Strict TDD for every future change.
- `.gitignore` updates for both stacks.

**Deferred to later changes:** auth wiring, admin route protection, real screens/pages, Gemini AI integration, actual Supabase migration schema content (0001-0004), Vercel/Fly.io provisioning, CI/CD config, Playwright e2e, TanStack Query wiring.

## Risks

- Docker Desktop availability on this Windows machine is unverified — required for `supabase start` (not for `supabase init`, which is filesystem-only).
- Two independent toolchains (npm/pnpm for frontend, uv for backend) mean `sdd-tasks` must pin two separate exact test-command strings plus a combined "both pass locally" verification step, since there is no CI in this first change.
- Migration filename convention mismatch (`0001-0004*.sql` chat shorthand vs Supabase CLI's timestamp-prefixed `supabase migration new` output) must be resolved explicitly in the proposal/design phase before any schema file is written.
- Fast-moving tooling (Tailwind v4 zero-config, shadcn CLI, Serwist) — versions should be pinned at scaffold time to avoid drift.

## Ready for Proposal

Yes. Scope is bounded, all research questions are answered with a concrete recommendation, and the critical Strict-TDD blocker (test runner choice) is resolved for both stacks.
