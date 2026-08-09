# Tasks: Initial Scaffolding

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines (hand-authored only) | ~500-750 |
| Estimated changed lines (incl. generated/vendored: lockfiles, shadcn/CLI boilerplate, supabase config.toml) | ~8,000-15,000+ |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 frontend -> PR2 backend -> PR3 supabase -> PR4 config |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main (user-confirmed) |

Decision needed before apply: Resolved — 4 chained PRs, stacked-to-main
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

**Counting basis**: the 400-line guard counts authored additions+deletions only (excludes generated goldens/lockfiles per guard convention), and hand-authored content alone (~500-750 lines across both stacks + config) already exceeds it. Raw diffs will additionally include `package-lock.json`, `uv.lock`, shadcn-generated UI components, and `supabase/config.toml` (thousands of lines) — mark these `linguist-generated` so reviewers can collapse them; they still count toward true diff size even though excluded from the authored risk figure.

### Suggested Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----|----|----|----|
| 1 | Frontend scaffold + Serwist caching + `/admin` NetworkOnly | PR1 | `npm --prefix frontend test` | `npm --prefix frontend run dev` (manual boot check) | delete `frontend/` |
| 2 | Backend scaffold + `products` domain + `/health` | PR2 | `uv run --project backend pytest -q` | N/A (no runtime harness scoped; TestClient covers `/health`) | delete `backend/` |
| 3 | Supabase init wiring | PR3 | N/A (no test framework for init) | N/A (filesystem-only, `supabase start` out of scope) | delete `supabase/` |
| 4 | Config wiring (`openspec/config.yaml`, `.gitignore`) | PR4 | both pinned commands sequentially | N/A (config-only) | `git checkout` both files |

## Phase 1: Frontend Scaffold
- [x] 1.1 `create-next-app@latest frontend` (TS, Tailwind 4.1.x, App Router, ESLint)
- [x] 1.2 `shadcn@latest init` + add Button component
- [x] 1.3 Install Vitest 3.2.x/RTL 16.3.x/jsdom 26.x; create `vitest.config.ts`, `vitest.setup.ts`
- [x] 1.4 RED: write `src/components/ui/__tests__/button.test.tsx`, run, confirm fails (no test wiring)
- [x] 1.5 GREEN: wire `package.json` test script so 1.4 passes
- [x] 1.6 REFACTOR: clean up test setup
- [x] 1.7 Install `serwist`/`@serwist/next` 9.2.x
- [x] 1.8 RED: write test asserting `/admin/*` requests use NetworkOnly (never cached); confirm fails (no SW config yet)
- [x] 1.9 GREEN: create `src/lib/pwa/runtime-caching.ts` (NetworkOnly /admin+non-GET first, NetworkFirst catalog, SWR /api/catalog, CacheFirst storage), `src/app/sw.ts`, `next.config.ts` withSerwist; pass 1.8
- [x] 1.10 REFACTOR: extract matcher constants
- [x] 1.11 Create `public/manifest.webmanifest`; modify `layout.tsx` metadata

## Phase 2: Backend Scaffold
- [x] 2.1 `uv init backend`; pin Python 3.13, FastAPI 0.118+, pytest 8.4.x, pytest-asyncio 1.2.x, httpx 0.28.x, ruff 0.14.x
- [x] 2.2 Create 6 domains x `domain/application/infrastructure` `__init__.py` (incl. `shared/application`)
- [x] 2.3 RED: write `tests/unit/products/test_product_domain.py`; confirm fails (module missing)
- [x] 2.4 GREEN: create `products/domain/product.py` dataclass+invariants, zero framework imports
- [x] 2.5 REFACTOR: add `products/application` use-case + `infrastructure` in-memory repo
- [x] 2.6 RED: write `tests/integration/api/test_health.py` (`TestClient` GET `/health`); confirm fails (no app)
- [x] 2.7 GREEN: create `src/gcell/main.py`, `/health` -> `200 {"status":"ok"}`
- [x] 2.8 REFACTOR: clean up app wiring

## Phase 3: Supabase Init
- [ ] 3.1 `supabase init`; verify `config.toml` exists, no schema SQL

## Phase 4: Config Wiring & Verification
- [ ] 4.1 Modify `openspec/config.yaml` `testing:` block + `rules.apply.tdd`/`verify`
- [ ] 4.2 Modify `.gitignore` (node_modules/, .next/, .venv/, __pycache__/, supabase/.temp/)
- [ ] 4.3 Write `backend/tests/architecture/test_domain_boundary.py` (AST-walk all 6 `domain/` dirs, ban fastapi/pydantic/supabase/sqlalchemy/httpx imports); confirm passes
- [ ] 4.4 Verify all 6 domains have `domain/application/infrastructure` subdirs
- [ ] 4.5 Run `npm --prefix frontend test` and `uv run --project backend pytest -q`; confirm both exit 0
- [ ] 4.6 Confirm `git status --porcelain` shows no ignored artifacts tracked
