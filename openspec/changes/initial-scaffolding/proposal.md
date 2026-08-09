# Proposal: Initial Scaffolding

> Session preflight: pace=interactive · artifact_store=hybrid · delivery_strategy=ask-on-risk · review_budget_lines=400

## Intent

The repository holds only agent tooling — no `package.json`, no `pyproject.toml`, no runnable app. `openspec/config.yaml` declares `strict_tdd: true` but `testing.status: not-yet-implemented` with every command field `null`, so **no future change can enter its TDD loop**. This change delivers the minimum runnable skeleton for both stacks and pins the two exact test commands that unblock Strict TDD for the rest of the project.

## Product Decisions (user-confirmed)

- **Definition of done**: scaffold defaults are sufficient — no branded placeholder homepage in this change. Visual identity is applied when real screens are designed.
- **Collaborators**: solo developer for now. No onboarding README in this slice; add one if/when a second contributor joins.
- **Worked hexagonal example domain**: `products`, confirmed — clearest invariants (variants, price, status) to demonstrate the domain/application/infrastructure boundary.
- **PWA offline intent**: offline catalog browsing is a near-term product goal, not a someday-maybe. The Serwist configuration in this change MUST be structured around a real runtime-caching strategy for catalog routes/data (not a bare installable-only shell) — see updated scope below. Full cache population still waits for real catalog pages to exist (later change), but the caching *architecture* is decided now so it isn't reworked later.

## Scope

### In Scope
- `frontend/`: `create-next-app@latest` (TS, Tailwind, App Router, ESLint) + `shadcn@latest init` + Serwist (`@serwist/next`, `@serwist/sw`) PWA skeleton with a **decided runtime-caching strategy for public catalog routes** (e.g. StaleWhileRevalidate for catalog pages/images) — architecture decided in `sdd-design`, but actual cache population deferred until real catalog pages exist — + Vitest/React Testing Library with one passing example test. Versions pinned exactly.
- `backend/`: uv-managed FastAPI project; hexagonal skeleton for 6 domains (`products`, `stock`, `content`, `ai`, `recommendation`, `shared`), each with `domain/`, `application/`, `infrastructure/`. One worked domain (`products`) with a passing pure-domain pytest unit test plus a passing `/health` integration test via `TestClient`.
- `supabase/`: `supabase init` only — `config.toml` and folder wiring, **no schema SQL**.
- `openspec/config.yaml`: fill `testing:` (both pinned commands, frameworks, layers, quality tools) and `rules.apply.tdd`/`verify` command fields.
- `.gitignore`: `node_modules/`, `.next/`, `.venv/`, `__pycache__/`, `supabase/.temp/`, plus standard entries for both stacks.

### Out of Scope
Auth wiring and admin route protection · real screens/pages beyond scaffold defaults · Gemini AI integration · Supabase schema migration content (`0001-0004`) · Vercel/Fly.io provisioning · any CI/CD · Playwright e2e · TanStack Query.

## Capabilities

### New Capabilities
- `platform-foundation`: repository topology, pinned per-stack verification commands, backend `/health` contract, hexagonal layer boundaries, and installable PWA shell.

### Modified Capabilities
- None (`openspec/specs/` is empty).

## Approach

Use each ecosystem's official generator, then prune to the bounded scope. Backend uses **uv** over Poetry for a faster local verify loop (no CI in this change). Frontend uses **Serwist** (maintained successor to `next-pwa`). One worked domain proves the hexagonal boundary — domain code imports no FastAPI/Pydantic/DB client. Supabase stays `init`-only because schema needs a data-model spec first.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `frontend/` | New | Next.js + Tailwind + shadcn + Serwist + Vitest |
| `backend/` | New | uv + FastAPI, 6 domain skeletons, `products` example |
| `supabase/` | New | `config.toml` wiring only |
| `openspec/config.yaml` | Modified | `testing:` block + apply/verify commands |
| `.gitignore` | Modified | Node + Python + Supabase entries |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Docker Desktop unverified on this Windows host | High | `supabase init` is filesystem-only; `supabase start` is out of scope |
| Migration naming: `0001-0004` vs CLI timestamp prefix | High | Unresolved — `sdd-design` MUST decide before any SQL |
| Fast-moving tooling drift (Tailwind v4, shadcn, Serwist) | Med | Pin exact versions; record them in the design |
| Two toolchains, no CI | Med | Pin two exact commands + a combined "both pass locally" step |
| Scaffold output exceeds the 400-line review budget | High | `sdd-tasks` forecasts; likely chained PRs (frontend / backend / config) |
| Offline caching strategy decided before real catalog pages exist | Med | `sdd-design` picks the Serwist runtime-caching strategy now; population of the cache is exercised once catalog routes are real, not in this change |

## Rollback Plan

Every deliverable is additive. Revert by deleting `frontend/`, `backend/`, `supabase/`, restoring `openspec/config.yaml` and `.gitignore` from git, and dropping the branch. No data, no deploy, no migration is touched, so rollback is a pure `git` operation.

## Dependencies

- Node.js + npm, Python 3.12+, `uv`, Supabase CLI installed locally.
- Docker Desktop only if local Supabase runtime is later attempted (not in this change).

## Success Criteria

- [ ] Frontend example test passes via the pinned command.
- [ ] Backend domain unit test and `/health` integration test pass via the pinned command.
- [ ] `openspec/config.yaml` `testing.status` is no longer `not-yet-implemented` and both commands are non-null.
- [ ] `supabase/config.toml` exists; `supabase/migrations/` contains no schema SQL.
- [ ] Fresh clone reaches both green test runs using only documented setup steps.
- [ ] No ignored artifact (`node_modules/`, `.venv/`, `.next/`) is tracked.
- [ ] Serwist config documents a concrete runtime-caching strategy for public catalog routes (decision recorded in `sdd-design`, even though cache population is exercised in a later change).
