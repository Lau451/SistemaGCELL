# Apply Progress: initial-scaffolding

> Persistence note: Engram MCP was disconnected for this run. Progress is
> persisted to OpenSpec only (`tasks.md` checkboxes + this file), per explicit
> fallback instruction for this session.

## Work Unit 1 — PR1: Frontend Scaffold

**Branch**: `pr1-frontend-scaffold` (off `main`, stacked-to-main chain, PR1 of 4)
**Status**: Complete — all Phase 1 tasks (1.1–1.11) done, all green.
**Scope boundary**: scaffold-only per user-confirmed constraint — shadcn default
generated `Button` and Next.js defaults used as-is. No brand colors, no custom
typography, no visual identity for the fundas-de-celulares business.

### Completed Tasks
- [x] 1.1 `create-next-app@latest frontend` (TS, Tailwind, App Router, ESLint)
- [x] 1.2 `shadcn@latest init` (base-nova preset) + Button component
- [x] 1.3 Installed Vitest/RTL/jsdom; created `vitest.config.mts`, `vitest.setup.ts`
- [x] 1.4 RED: `src/components/ui/__tests__/button.test.tsx` written, confirmed failing (`Missing script: "test"`)
- [x] 1.5 GREEN: wired `"test": "vitest run"` in `package.json`; 3/3 passed
- [x] 1.6 REFACTOR: renamed config to `vitest.config.mts`, fixed `__dirname` → `import.meta.dirname`; still 3/3 passing, zero config warnings
- [x] 1.7 Installed `serwist` + `@serwist/next` (no separate `@serwist/sw` — folded into `serwist` in v9, per design.md)
- [x] 1.8 RED: `src/lib/pwa/__tests__/runtime-caching.test.ts` written, confirmed failing (module not found)
- [x] 1.9 GREEN: created `src/lib/pwa/runtime-caching.ts` (matcher matrix), `src/app/sw.ts`, `next.config.ts` with `withSerwist`; 4/4 passed
- [x] 1.10 REFACTOR: extracted shared `Matcher` type alias (`RouteMatchCallbackOptions`) instead of repeating the inline options type per matcher; fixed test's fragile `Parameters<>` extraction to use the same public type. Still 4/4 passing, zero type errors.
- [x] 1.11 Created `public/manifest.webmanifest`; added `metadata.manifest` + `viewport.themeColor` to `layout.tsx`

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.4/1.5/1.6 | `src/components/ui/__tests__/button.test.tsx` | Unit (RTL) | N/A (new) | ✅ Written, confirmed failing via `npm --prefix frontend test` → `Missing script: "test"` | ✅ 3/3 passed after wiring `test` script | ✅ 3 cases (renders accessible name, click handler fires once, disabled blocks click) | ✅ Renamed `.ts`→`.mts`, `__dirname`→`import.meta.dirname`; 0 warnings |
| 1.8/1.9/1.10 | `src/lib/pwa/__tests__/runtime-caching.test.ts` | Unit | N/A (new) | ✅ Written, confirmed failing — `Failed to resolve import "@/lib/pwa/runtime-caching"` | ✅ 4/4 passed after implementing the matcher matrix | ✅ 4 cases (admin GET, admin sub-route, non-GET catalog POST, public catalog GET must NOT be NetworkOnly) | ✅ Extracted `Matcher` type alias from `RouteMatchCallbackOptions`; simplified test helper's typing to match |

### Test Summary
- **Total tests written**: 7
- **Total tests passing**: 7
- **Layers used**: Unit (7), Integration (0), E2E (0)
- **Approval tests** (refactoring): None — no refactoring-of-existing-code tasks in this unit
- **Pure functions created**: 4 matcher predicates (`isAdminOrMutatingRequest`, `isCatalogPageNavigation`, `isCatalogApiRead`, `isSupabaseStoragePublicObject`) — all pure, all directly unit-tested without mocks

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `npm --prefix frontend test` → `Test Files 2 passed (2)`, `Tests 7 passed (7)` |
| Runtime harness command/scenario and exact result | `npm run build` (`next build --webpack`) → compiled successfully, service worker bundled at `/sw.js`; then `npm start` and curled `/` (200), `/sw.js` (200), `/manifest.webmanifest` (200) — no runtime errors |
| Rollback boundary | Delete `frontend/` — fully additive, no other tracked files depend on it in this PR |

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `frontend/` (create-next-app output) | Created | Next.js 16.3.0 App Router + TS + Tailwind 4 + ESLint scaffold |
| `frontend/components.json`, `src/components/ui/button.tsx`, `src/lib/utils.ts` | Created | `shadcn@latest init -d` (base-nova preset) |
| `frontend/vitest.config.mts`, `vitest.setup.ts` | Created | jsdom env, `@testing-library/jest-dom` setup |
| `frontend/src/components/ui/__tests__/button.test.tsx` | Created | RTL example test (3 behavioral assertions) |
| `frontend/next.config.ts` | Modified | Wrapped with `withSerwist({ swSrc: "src/app/sw.ts", swDest: "public/sw.js" })` |
| `frontend/src/app/sw.ts` | Created | Serwist service worker entry: precache manifest + `catalogRuntimeCaching` + `defaultCache` |
| `frontend/src/lib/pwa/runtime-caching.ts` | Created | Order-sensitive matcher matrix (NetworkOnly admin/non-GET first, NetworkFirst catalog pages → SWR catalog API → CacheFirst Supabase Storage images) |
| `frontend/src/lib/pwa/__tests__/runtime-caching.test.ts` | Created | 4 behavioral tests on the matcher matrix |
| `frontend/public/manifest.webmanifest` | Created | Installable-shell metadata (neutral defaults, no brand palette) |
| `frontend/src/app/layout.tsx` | Modified | Added `metadata.manifest` + `viewport.themeColor` |
| `frontend/package.json` | Modified | `test` script; `dev`/`build` scripts pinned to `--webpack` (see Deviations) |
| `frontend/.gitignore`, `frontend/eslint.config.mjs` | Modified | Ignore generated `public/sw.js`/`sw.js.map` (build artifact, not source) |

### Status
11/11 Phase 1 tasks complete. Ready for verify (of this PR1 slice) or for PR2 (Backend Scaffold) to begin.

## Work Unit 2 — PR2: Backend Scaffold

**Branch**: `pr2-backend-scaffold` (branched from `main`, PR2 of 4)
**Status**: Complete — all Phase 2 tasks (2.1–2.8) done, all green.

### Completed Tasks
- [x] 2.1 `uv init backend --package --name gcell --python 3.13` (src layout); pinned FastAPI, pytest, pytest-asyncio, httpx, ruff as dev/runtime deps
- [x] 2.2 Created 6 domains (`products`, `stock`, `content`, `ai`, `recommendation`, `shared`) x `domain/`, `application/`, `infrastructure/`, each with `__init__.py` (incl. `shared/application/` as an empty package per design.md's correction)
- [x] 2.3 RED: `backend/tests/unit/products/test_product_domain.py` written, confirmed failing (`ModuleNotFoundError: No module named 'gcell.products.domain.product'`)
- [x] 2.4 GREEN: `backend/src/gcell/products/domain/product.py` — `Product`/`ProductVariant` dataclasses with `__post_init__` invariants (blank name/phone_model rejected, negative price/cost rejected); zero framework imports (verified via grep for fastapi/pydantic/sqlalchemy/httpx/supabase — no matches)
- [x] 2.5 REFACTOR: added `products/application/repository.py` (`ProductRepository` Protocol port), `products/application/register_product.py` (`RegisterProductUseCase`), `products/infrastructure/in_memory_product_repository.py` (`InMemoryProductRepository`); added `backend/tests/unit/products/test_register_product_use_case.py` to keep the new application/infra code test-covered (not a bare stub)
- [x] 2.6 RED: `backend/tests/integration/api/test_health.py` written, confirmed failing (`ModuleNotFoundError: No module named 'gcell.main'`)
- [x] 2.7 GREEN: `backend/src/gcell/main.py` — FastAPI app, `GET /health` -> `200 {"status":"ok"}`; 1/1 passed
- [x] 2.8 REFACTOR: extracted the health route into `backend/src/gcell/api/health.py` (`APIRouter`) and `include_router`'d it from `main.py`, separating the composition root from route definitions ahead of future domain routers; also removed unused `[project.scripts]` CLI entrypoint boilerplate left by `uv init` (dead code for a web service project) and emptied `gcell/__init__.py` to match the other package `__init__.py` files

### Test Summary
- **Total tests written**: 8 (5 domain invariant tests + 2 application/repo tests + 1 health integration test)
- **Total tests passing**: 8/8
- **Layers used**: Unit (7: 5 domain + 2 application), Integration (1: `/health` via `TestClient`)

### Status
8/8 Phase 2 tasks complete. Ready for verify (of this PR2 slice) or for PR3 (Supabase Init) to begin.

## Work Unit 3 — PR3: Supabase Init

**Branch**: `pr3-supabase-init` (off `main`, PR3 of 4)
**Status**: Complete — task 3.1 done.
**Tooling note**: Supabase CLI was not installed on this machine; used `npx -y supabase@latest` (resolved to 2.113.0) instead of a global install, since a one-off `init` doesn't need a persistent install.

### Completed Tasks
- [x] 3.1 `npx supabase@latest init --workdir .` — created `supabase/config.toml` and `supabase/.gitignore` only. Verified via `find supabase -type f`: no `migrations/` directory, no schema SQL. `config.toml` inspected for secrets before committing — none present (local dev ports/defaults only, `project_id = "SistemaGCELL"`).

### Status
1/1 Phase 3 task complete. Ready for PR4 (Config Wiring & Verification) to begin.

## Work Unit 4 — PR4: Config Wiring & Verification

**Branch**: `pr4-config-wiring` (off the locally-integrated `main`, PR4 of 4 — final PR)
**Status**: Complete — all 6 Phase 4 tasks done.

### Completed Tasks
- [x] 4.1 `openspec/config.yaml` `testing:` block: `status: implemented`, both commands pinned (`npm --prefix frontend test`, `uv run --project backend pytest -q`). `rules.apply`/`rules.verify` restructured as `{frontend, backend}` objects.
- [x] 4.2 Root `.gitignore` hardened with Node/Python/Supabase/env/OS entries as defense-in-depth on top of each stack's own nested `.gitignore` (already present from PR1/PR2/PR3).
- [x] 4.3 `backend/tests/architecture/test_domain_boundary.py` — AST-walk test (real `ast` module parsing, not regex) banning fastapi/pydantic/supabase/sqlalchemy/httpx imports in any of the 6 domains' `domain/` layer. RED confirmed (temporarily added a violating import, test failed with the exact violation reported), then GREEN after removing it.
- [x] 4.4 Verified all 18 domain/application/infrastructure subdirectories exist across the 6 domains.
- [x] 4.5 Both pinned commands run for real: frontend 7/7 passed, backend 9/9 passed (the new architecture test plus the 8 from PR2).
- [x] 4.6 `git status --porcelain` clean; spot-checked `git check-ignore -v` for node_modules/.venv/.next/__pycache__/supabase temp dirs — all correctly ignored via nested gitignores, root additions are redundant-but-correct defense-in-depth.

### Status
6/6 Phase 4 tasks complete. `initial-scaffolding` apply phase is now fully done (4/4 PRs). Strict TDD is unblocked project-wide. Ready for `sdd-verify`.

