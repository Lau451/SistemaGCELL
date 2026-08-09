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
| `frontend/src/lib/pwa/runtime-caching.ts` | Created | Order-sensitive matcher matrix (NetworkOnly admin/non-GET → NetworkFirst catalog pages → SWR catalog API → CacheFirst Supabase Storage images) |
| `frontend/src/lib/pwa/__tests__/runtime-caching.test.ts` | Created | 4 behavioral tests on the matcher matrix |
| `frontend/public/manifest.webmanifest` | Created | Installable-shell metadata (neutral defaults, no brand palette) |
| `frontend/src/app/layout.tsx` | Modified | Added `metadata.manifest` + `viewport.themeColor` |
| `frontend/package.json` | Modified | `test` script; `dev`/`build` scripts pinned to `--webpack` (see Deviations) |
| `frontend/.gitignore`, `frontend/eslint.config.mjs` | Modified | Ignore generated `public/sw.js`/`sw.js.map` (build artifact, not source) |

### Versions Actually Installed (re-verified at install time, 2026-08-09)

Design.md pins were explicitly marked "best known at design time, not frozen." Re-verified against npm `latest` dist-tags at install time:

| Package | Design pin | Actually installed | Note |
|---|---|---|---|
| `next` / `create-next-app` | 16.x | **16.3.0** | Matches |
| `react` / `react-dom` | 19.2 | **19.2.8** | Matches (create-next-app default) |
| `typescript` | 5.9.x | **^5** (resolved latest 5.x) | Matches range |
| `tailwindcss` | 4.1.x | **^4** (create-next-app default, resolves to 4.x latest) | Matches |
| `shadcn` CLI | `shadcn@latest` (3.x) | **4.16.2** | Deviation — shadcn CLI is now on major 4, not 3. Used `shadcn@latest` per design's own instruction to use "latest", so this is the correct resolution, just a higher major than the design doc's stale note. |
| `serwist` / `@serwist/next` | 9.2.x | **9.5.12** | Matches major; newer minor. No `@serwist/sw` installed — confirmed folded into `serwist` in v9 per design.md decision. |
| `vitest` | 3.2.x | **4.1.10** | **Deviation** — Vitest 4.1.10 is genuinely the current stable `latest` dist-tag (confirmed via `npm view vitest dist-tags`, not a prerelease). 3.x is tagged `V3` (previous major), not `latest`. Installed 4.x per design's explicit re-verify-at-install-time instruction. |
| `@vitejs/plugin-react` | 5.x | **5.2.0** | Matches design pin. Deliberately did NOT install the nominal "latest" 6.0.5 — it depends on `@rolldown/plugin-babel` which requires `@babel/core@^8`, conflicting with `shadcn`'s own `@babel/preset-typescript@^7` dependency (npm peer-dependency resolution error). 5.2.0 is the newest 5.x, has no such conflict, and supports Vite 7/8. |
| `@testing-library/react` | 16.3.x | **16.3.2** | Matches |
| `@testing-library/jest-dom` | 6.6.x | **7.0.0** | **Deviation** — 7.0.0 is the current `latest` dist-tag (confirmed), 6.x is superseded. Installed 7.x. |
| `jsdom` | 26.x | **^29.1.1** (npm-resolved; registry `latest` is 30.0.1) | **Deviation** — installed via unpinned `npm install jsdom`, npm's resolver picked 29.1.1 as satisfying peer ranges from the installed toolchain; registry `latest` is actually 30.0.1. Either resolves fine for this scaffold; recorded as installed for traceability. |

### Deviations from Design

1. **Vitest 4.x instead of 3.2.x, `@testing-library/jest-dom` 7.x instead of 6.6.x** — design.md explicitly instructs re-verifying latest stable at install time since its pins are "a drift baseline, not frozen forever." Confirmed via `npm view <pkg> dist-tags` that these are genuinely the current `latest` (not beta/preview) releases, so installed the truly-current versions rather than the stale design-time pins.
2. **`@vitejs/plugin-react` pinned to 5.2.0, not the nominal-latest 6.0.5** — 6.0.5 introduced a hard peer-dependency conflict (`@babel/core@^8` via `@rolldown/plugin-babel`) against `shadcn`'s own `@babel/preset-typescript@^7`, which `npm install` refused to resolve without `--force`/`--legacy-peer-deps`. Rather than silently overriding a real peer conflict, pinned to the newest 5.x (matches design's original 5.x pin) which has no such conflict and is still current/maintained.
3. **`dev`/`build` npm scripts explicitly pinned to `--webpack`** (not in design.md — a real gap discovered during implementation). Next.js 16 defaults to Turbopack. `@serwist/next` v9 (the version design.md explicitly pins, as opposed to the experimental `@serwist/turbopack`) injects a webpack-only config function; running an unmodified `next build`/`next dev` under Turbopack fails hard (`ERROR: This build is using Turbopack, with a 'webpack' config and no 'turbopack' config`). Fixed by adding `--webpack` to both scripts. Verified end-to-end: `npm run build` compiles and bundles `/sw.js` successfully; `npm start` boots and serves `/`, `/sw.js`, and `/manifest.webmanifest` all at `200`.
4. **`frontend/.gitignore` and `frontend/eslint.config.mjs` modified beyond the design's file list** — the generated `public/sw.js` (Serwist's build output) was initially being linted by ESLint (1 real error, 86 warnings — it's a minified bundle, not source) and would have been a trackable build artifact. Added it to both ignore lists; this is scaffold hygiene, not a scope change.
5. **shadcn CLI installed at major 4 (4.16.2), not the 3.x the design doc's version table lists.** Design's own instruction was to use `shadcn@latest`, which is what was run; the table's "3.x" note was simply stale versus the doc's own re-verify directive.

None of these deviations touch product/design decisions (routing, caching strategy, or component behavior) — all are toolchain-version and build-tooling reconciliations required to make the pinned architecture actually run on 2026-08-09's package registry state.

### Issues Found
None blocking. The Turbopack/webpack conflict (deviation 3) is worth flagging forward to PR4 (config wiring) and to whoever eventually adds CI, since `npm --prefix frontend run dev`/`build` now always forces webpack — if a future change wants Turbopack for dev speed, `@serwist/turbopack` (experimental) would need to be evaluated instead of `@serwist/next`.

### Remaining Tasks (out of scope for this PR)
- [ ] Phase 2: Backend Scaffold (2.1–2.8) — PR2
- [ ] Phase 3: Supabase Init (3.1) — PR3
- [ ] Phase 4: Config Wiring & Verification (4.1–4.6) — PR4

### Workload / PR Boundary
- Mode: stacked-to-main chained PR slice (PR1 of 4)
- Current work unit: Unit 1 — Frontend scaffold + Serwist caching + `/admin` NetworkOnly
- Boundary: starts from empty repo (no `frontend/`), ends with a fully green, buildable, installable-shell Next.js app with the decided runtime-caching matrix in place. Does not touch `backend/`, `supabase/`, or `openspec/config.yaml`.
- Estimated review budget impact: ~29 authored/generated files under `frontend/`; hand-authored non-generated lines (config, sw.ts, runtime-caching.ts + tests, manifest, layout diff) are well under the 400-line authored-changes guard. `package-lock.json` is generated and should be marked `linguist-generated` by the reviewer per the tasks.md forecast note.

### Status
11/11 Phase 1 tasks complete. Ready for verify (of this PR1 slice) or for PR2 (Backend Scaffold) to begin.

## PR2

## Work Unit 2 — PR2: Backend Scaffold

**Branch**: `pr2-backend-scaffold` (branched from `main`, NOT from
`pr1-frontend-scaffold` — no merge/rebase onto the PR1 branch, per explicit
instruction for this PR). `openspec/changes/initial-scaffolding/` did not
exist on `main` (it was only added on `pr1-frontend-scaffold`), so its
content was pulled into this branch via
`git checkout pr1-frontend-scaffold -- openspec/changes/initial-scaffolding`
(a working-tree content copy, not a merge or rebase — no ancestry link to
`pr1-frontend-scaffold` was created). See **Deviations** below — this means
PR2's diff will show the whole `openspec/changes/initial-scaffolding/`
directory as new versus `main`, which is a real overlap with PR1's diff on
those bookkeeping files, contradicting the "no file overlap" premise given
for this PR. Product code (`backend/` vs `frontend/`) has zero overlap.
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

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | REFACTOR |
|------|-----------|-------|------------|-----|-------|----------|
| 2.3/2.4/2.5 | `backend/tests/unit/products/test_product_domain.py`, `test_register_product_use_case.py` | Unit (pure domain + application) | N/A (new) | ✅ Confirmed failing via `uv run --project backend pytest -q` → `ModuleNotFoundError: No module named 'gcell.products.domain.product'` | ✅ 5/5 passed after `product.py`; 7/7 passed after adding application/infra + its own test | ✅ Added `application`/`infrastructure` layers on top of the proven domain type; re-ran full suite, still 7/7 (later 8/8 with health test) |
| 2.6/2.7/2.8 | `backend/tests/integration/api/test_health.py` | Integration (`fastapi.testclient.TestClient`) | N/A (new) | ✅ Confirmed failing — `ModuleNotFoundError: No module named 'gcell.main'` | ✅ 1/1 passed after `main.py` with inline `/health` route | ✅ Extracted route into `api/health.py` `APIRouter`, `main.py` now composition-root-only; re-ran full suite, still 8/8 passing, ruff clean |

### Test Summary
- **Total tests written**: 8 (5 domain invariant tests + 2 application/repo tests + 1 health integration test)
- **Total tests passing**: 8/8
- **Layers used**: Unit (7: 5 domain + 2 application), Integration (1: `/health` via `TestClient`)
- **Pure functions/types created**: `Product`, `ProductVariant` dataclasses (domain); `ProductRepository` Protocol, `RegisterProductUseCase` (application); `InMemoryProductRepository` (infrastructure) — domain layer has zero framework imports, verified by grep

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run --project backend pytest -q` → `8 passed, 1 warning in 0.26s` (warning is an unrelated `StarletteDeprecationWarning` about `httpx`/`starlette.testclient`, see Issues Found) |
| Runtime harness command/scenario and exact result | N/A per tasks.md's own scoping — no runtime harness assigned to this unit; `fastapi.testclient.TestClient` (used in `test_health.py`) already exercises the ASGI app end-to-end without a live server, which is the integration boundary this unit owns |
| Rollback boundary | Delete `backend/` — fully additive, no other tracked files depend on it in this PR (the `openspec/changes/initial-scaffolding/` bookkeeping files are pre-existing content pulled in from PR1, not new dependencies created by this unit) |

### Files Changed
| File | Action | What Was Done |
|------|--------|---------------|
| `backend/pyproject.toml`, `backend/uv.lock`, `backend/README.md`, `backend/.python-version` | Created | `uv init --package` project; FastAPI runtime dep; pytest/pytest-asyncio/httpx/ruff dev deps; `[tool.pytest.ini_options]` (`asyncio_mode=auto`, `testpaths=["tests"]`); `[tool.ruff]`/`[tool.ruff.lint]` |
| `backend/.gitignore` | Created | Ignores `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/` — `uv init` did not generate one in this repo (existing git repo, `--vcs none`); not in design.md's file list but necessary scaffolding hygiene, same category as PR1's `frontend/.gitignore` deviation |
| `backend/src/gcell/{products,stock,content,ai,recommendation,shared}/{domain,application,infrastructure}/__init__.py` | Created | 6 domains x 3 layers, all empty packages except `products` |
| `backend/src/gcell/products/domain/product.py` | Created | `Product`/`ProductVariant` dataclasses with invariants |
| `backend/src/gcell/products/application/repository.py`, `register_product.py` | Created | `ProductRepository` port (Protocol) + `RegisterProductUseCase` |
| `backend/src/gcell/products/infrastructure/in_memory_product_repository.py` | Created | `InMemoryProductRepository` adapter |
| `backend/src/gcell/main.py` | Created | FastAPI app composition root, includes `health_router` |
| `backend/src/gcell/api/__init__.py`, `api/health.py` | Created | `/health` `APIRouter` (`GET /health` -> `200 {"status":"ok"}`) |
| `backend/src/gcell/__init__.py` | Modified | Emptied — removed `uv init`'s placeholder `main()` CLI stub (unused, misleading for a web service project) |
| `backend/tests/unit/products/test_product_domain.py`, `test_register_product_use_case.py` | Created | Pure-domain + application unit tests, zero FastAPI imports |
| `backend/tests/integration/api/test_health.py` | Created | `TestClient` integration test for `/health` |

### Versions Actually Installed (re-verified at install time, 2026-08-09)

Design.md pins were explicitly marked "best known at design time, not frozen." Re-verified by letting `uv add` resolve unconstrained (then pinning the resolved floor with `>=`):

| Package | Design pin | Actually installed | Note |
|---|---|---|---|
| Python | 3.13 | **3.13.12** | Matches (installed via `uv python install 3.13`) |
| `uv` | 0.9.x | **0.10.11** | Deviation — 0.10.11 is the CLI's own current version on this machine; not a project dependency, informational only |
| `fastapi` | 0.118+ | **0.141.1** | Matches floor; genuinely current `latest` |
| `pytest` | 8.4.x | **9.1.1** | **Deviation** — pytest 9.x is the current major/`latest` as of 2026-08-09, same category as PR1's Vitest 3.x→4.x deviation. Installed current-latest per design's own re-verify-at-install-time instruction. |
| `pytest-asyncio` | 1.2.x | **1.4.0** | Newer minor within the same major; matches design intent |
| `httpx` | 0.28.x | **0.28.1** | Matches exactly |
| `ruff` | 0.14.x | **0.16.2** | Newer minor; current `latest` |

### Deviations from Design

1. **Test file paths use `backend/tests/unit/<domain>/` and `backend/tests/integration/api/`, not design.md's flat `backend/tests/products/test_product_domain.py` / `backend/tests/test_health.py`.** This PR's explicit instructions specified the `unit/`+`integration/api/` layout convention, which is more scalable across the other 5 domains than design.md's flat layout; tasks.md has been updated to reflect the actual paths used.
2. **pytest 9.x / ruff 0.16.x instead of design's 8.4.x / 0.14.x pins** — re-verified as genuinely `latest` at install time (design.md's own instruction), same pattern as PR1's Vitest/jest-dom deviations.
3. **`backend/.gitignore` created** (not in design's file list) — necessary so `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/` are never accidentally staged; the root `.gitignore` Node/Python/Supabase entries are Phase 4's job (PR4), not yet in place, so backend needed its own interim ignore file. Same category as PR1's `frontend/.gitignore` deviation.
4. **Removed `uv init`'s default `[project.scripts]` CLI entrypoint and `gcell/__init__.py`'s placeholder `main()`** — not part of any design/task instruction, but this is dead boilerplate for a web-service project (a `gcell` console script that prints `"Hello from gcell!"` has no purpose here) and was cleaned up as part of task 2.8's REFACTOR step.
5. **`openspec/changes/initial-scaffolding/` pulled into this branch via `git checkout pr1-frontend-scaffold -- <path>`, not authored fresh** — see the Work Unit header note above. This is a genuine deviation from the "PR2 has no file overlap with PR1" premise stated for this task; flagged here and in the top-level risks.

None of these deviations touch product/architecture decisions (domain boundaries, invariants, or the `/health` contract) — all are toolchain-version, file-layout, or scaffolding-hygiene reconciliations.

### Issues Found
1. `fastapi.testclient.TestClient` emits `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead` on this FastAPI/Starlette version pair. Non-blocking (test still passes), but worth flagging forward: a future PR touching backend test infra may need `httpx2` once Starlette actually drops the `httpx`-backed `TestClient`.
2. See Deviation 5 above — the `openspec/changes/initial-scaffolding/` file overlap between PR1 and PR2 should be resolved by the reviewer before both PRs are opened on GitHub: either rebase PR2 onto PR1 (if PR1 merges first) or squash/exclude the bookkeeping-only overlap so the real GitHub diff isn't misleading.

### Remaining Tasks (out of scope for this PR)
- [ ] Phase 3: Supabase Init (3.1) — PR3
- [ ] Phase 4: Config Wiring & Verification (4.1–4.6) — PR4 (includes task 4.3, the architecture-boundary AST-walk test, deliberately NOT written in PR2 even though `backend/src/gcell/*/domain/` already has zero framework imports)

### Workload / PR Boundary
- Mode: stacked-to-main chained PR slice (PR2 of 4)
- Current work unit: Unit 2 — Backend scaffold + `products` domain + `/health`
- Boundary: starts from `main` (no `backend/`), ends with a fully green `uv`-managed FastAPI hexagonal skeleton (6 domains, `products` worked example, `/health` endpoint). Does not touch `frontend/`, `supabase/`, or `openspec/config.yaml`.
- Estimated review budget impact: hand-authored backend source + tests are well under the 400-line authored-changes guard (~14 small files, mostly under 40 lines each); `backend/uv.lock` is generated and should be marked `linguist-generated` by the reviewer, same as PR1's `package-lock.json`.

### Status
8/8 Phase 2 tasks complete. Ready for verify (of this PR2 slice) or for PR3 (Supabase Init) to begin. See Issues Found #2 before opening the real GitHub PR.

## Bookkeeping Restructure (between PR2 and PR3)

PR1 and PR2 each independently duplicated `openspec/changes/initial-scaffolding/` in their own branch history (PR2 copied it wholesale from PR1 to update its own checkboxes). Resolved by landing the shared SDD bookkeeping directly on `main` and rebasing both `pr1-frontend-scaffold` and `pr2-backend-scaffold` onto it — each branch now contains only its own code (`frontend/` / `backend/`), verified via `git diff main...<branch> --name-only` and confirmed both test suites still green post-rebase (frontend 7/7, backend 8/8). Full detail in `state.yaml` under `bookkeeping_restructure`.

**Going forward**: tasks.md/apply-progress.md/state.yaml updates for PR3 and PR4 are applied directly on `main` by the orchestrator, not inside the PR branches — except `openspec/config.yaml`'s `testing:` block, which is real PR4 deliverable content per the proposal and stays inside PR4's branch.

## Work Unit 3 — PR3: Supabase Init

**Branch**: `pr3-supabase-init` (off `main`, PR3 of 4)
**Status**: Complete — task 3.1 done.
**Tooling note**: Supabase CLI was not installed on this machine; used `npx -y supabase@latest` (resolved to 2.113.0) instead of a global install, since a one-off `init` doesn't need a persistent install.

### Completed Tasks
- [x] 3.1 `npx supabase@latest init --workdir .` — created `supabase/config.toml` and `supabase/.gitignore` only. Verified via `find supabase -type f`: no `migrations/` directory, no schema SQL. `config.toml` inspected for secrets before committing — none present (local dev ports/defaults only, `project_id = "SistemaGCELL"`).

### Workload / PR Boundary
- Mode: stacked-to-main chained PR slice (PR3 of 4)
- Boundary: adds `supabase/` only (2 files, 422 lines — both fully generated by the CLI, no hand-authored content). Does not touch `frontend/`, `backend/`, or `openspec/`.

### Status
1/1 Phase 3 task complete. Ready for PR4 (Config Wiring & Verification) to begin.

## Integration note (before PR4)

PR4's tasks (4.3-4.6) need `frontend/`, `backend/`, and `supabase/` present simultaneously — they can't be verified from a branch containing only `main`'s prior content. Merged `pr1-frontend-scaffold`, `pr2-backend-scaffold`, and `pr3-supabase-init` into `main` locally (three clean disjoint-file merges, no conflicts, nothing pushed to origin) before branching `pr4-config-wiring` from the result.

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

### Workload / PR Boundary
- Mode: stacked-to-main chained PR slice (PR4 of 4, final)
- Boundary: `openspec/config.yaml`, root `.gitignore`, one new test file. ~118 insertions, 16 deletions — well under the 400-line authored guard.
- Unlike PR1-3, this branch was NOT created from a disjoint-file base — it required PR1+PR2+PR3 merged first, since verification tasks need the full tree.

### Status
6/6 Phase 4 tasks complete. `initial-scaffolding` apply phase is now fully done (4/4 PRs). Strict TDD is unblocked project-wide. Ready for `sdd-verify`.
