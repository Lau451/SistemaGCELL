# Tasks: Admin Panel Authentication

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~700-850 (prod ~350-400, tests ~350-450) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 backend JWT+DB guard → PR2 frontend session/proxy infra → PR3 login pages + API proxy route + E2E |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Backend JWT verify + `require_db_pool` + `/admin/products` | PR 1 | `cd backend && uv run pytest tests/unit/shared/test_auth.py tests/unit/shared/test_dependencies.py tests/integration/api/test_admin.py tests/integration/api/test_lifespan.py tests/integration/api/test_health.py -v` | `curl` against local `uvicorn` with a minted test token (no live Supabase needed) | Revert `auth.py`, `dependencies.py`, `api/admin.py`, `main.py` router line, `pyproject.toml` dep |
| 2 | Frontend session/proxy infra, no pages yet | PR 2 | `cd frontend && npm test -- redirect.test.ts catalog-route-conformance.test.ts` | `npm run dev`; unauthenticated visit to `/admin/products` → confirm `307 → /admin/login?next=...` | Revert `proxy.ts`, `proxy-client.ts`, `redirect.ts`, `env.ts`, appended export in `server.ts` |
| 3 | Login/admin pages, `/api/admin/products`, E2E | PR 3 | `cd frontend && npm test -- route.test.ts` | Manual E2E: login → `/admin/products` renders rows (no Playwright suite exists) | Revert `app/(admin)/admin/**`, `app/api/admin/products/route.ts` |

## Phase 0: Prerequisite (blocking, manual)

- [ ] 0.1 Provision admin user: `POST http://127.0.0.1:54321/auth/v1/signup` (design.md curl); verify confirmed via Studio or `GET /auth/v1/user`.
- [ ] 0.2 Decode a real token for that user; confirm `alg`/`iss`/`aud` match assumed HS256 / `http://127.0.0.1:54321/auth/v1` / `authenticated`. Correct `verify_admin_jwt` config if not.

## Phase 1: Backend — JWT Verification & DB Guard (PR 1)

- [ ] 1.1 RED `backend/tests/unit/shared/test_auth.py`: `make_admin_token` factory; cases missing token, non-Bearer, expired, wrong `iss`, wrong `aud`, tampered signature, missing `exp`, `alg="none"` — all 401, identical body.
- [ ] 1.2 GREEN `backend/src/gcell/shared/infrastructure/config.py`: add `jwt_secret()`, `jwt_issuer()`, `jwt_audience()`.
- [ ] 1.3 GREEN `backend/src/gcell/shared/infrastructure/auth.py`: `AdminIdentity`, `verify_admin_jwt` (PyJWT, `algorithms=["HS256"]`, require `exp/iss/aud/sub`).
- [ ] 1.4 Add `pyjwt>=2.10` to `backend/pyproject.toml`; update `uv.lock`.
- [ ] 1.5 RED `backend/tests/unit/shared/test_dependencies.py`: `require_db_pool` — `None` pool → 503.
- [ ] 1.6 GREEN `backend/src/gcell/shared/infrastructure/dependencies.py`: `require_db_pool`.
- [ ] 1.7 RED `backend/tests/integration/api/test_admin.py`: bad token+`pool=None`→401 (order proof); valid token+`pool=None`→503; valid token+pool→200 via `list_all` spy.
- [ ] 1.8 GREEN `backend/src/gcell/api/admin.py`: router, `GET /admin/products`, response model.
- [ ] 1.9 Wire `backend/src/gcell/main.py`: `include_router(admin_router)`; refresh lifespan comment.
- [ ] 1.10 Add `JWT_SECRET`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` to `backend/.env.example`.
- [ ] 1.11 Regression: run `test_lifespan.py`/`test_health.py` unmodified, confirm green.
- [ ] 1.12 Add literal `asyncpg` entry to `BANNED_MODULES` domain-boundary fixture.

## Phase 2: Frontend — Session & Proxy Infrastructure (PR 2)

- [ ] 2.1 RED `frontend/src/lib/admin/__tests__/redirect.test.ts`: `isSafeAdminPath` rejects `//evil.com`, `/\evil.com`, `https://evil`, `/adminx`, `/catalog`; accepts `/admin`, `/admin/products?x=1`.
- [ ] 2.2 GREEN `frontend/src/lib/admin/redirect.ts`: `isSafeAdminPath()`.
- [ ] 2.3 GREEN `frontend/src/lib/admin/env.ts`: `getBackendUrl()` (default `http://127.0.0.1:8000`).
- [ ] 2.4 GREEN (append only) `frontend/src/lib/supabase/server.ts`: add `createSessionClient()`; do not touch existing two factories.
- [ ] 2.5 GREEN `frontend/src/lib/supabase/proxy-client.ts`: `createProxyClient(req, res)`, two-arg `setAll(cookies, headers)` applying cache-suppressing headers.
- [ ] 2.6 GREEN `frontend/src/proxy.ts`: `export function proxy(request)`, `matcher: ["/admin/:path*"]`, `getClaims()` gate, `/admin/login` pass-through/redirect rules, `next=` param.
- [ ] 2.7 Add `BACKEND_URL` to `frontend/.env.example`.
- [ ] 2.8 RED extend `frontend/src/lib/pwa/__tests__/catalog-route-conformance.test.ts`: assert `/admin`, `/admin/login`, `/admin/products`, `/api/admin/products` resolve `NetworkOnly`; assert `runtime-caching.ts` unmodified (pinned hash).
- [ ] 2.9 Verify: 2.8 passes with zero edits to `runtime-caching.ts`.

## Phase 3: Login Page, Admin Pages, API Proxy Route (PR 3)

- [ ] 3.1 RED `frontend/src/app/api/admin/products/__tests__/route.test.ts`: no claims→401 JSON, `fetch` never called; claims→one call with `Authorization: Bearer`; network throw→502.
- [ ] 3.2 GREEN `frontend/src/app/api/admin/products/route.ts` per design.
- [ ] 3.3 GREEN `frontend/src/app/(admin)/admin/login/page.tsx`: form + `signInAction` (generic error only, safe-`next` redirect).
- [ ] 3.4 GREEN `frontend/src/app/(admin)/admin/layout.tsx`: shell + `signOutAction`.
- [ ] 3.5 GREEN `frontend/src/app/(admin)/admin/page.tsx`: landing.
- [ ] 3.6 GREEN `frontend/src/app/(admin)/admin/products/page.tsx`: consumes `/api/admin/products`.

## Phase 4: End-to-End Verification

- [ ] 4.1 One true E2E: log in with the provisioned admin user, confirm redirect into `/admin`, confirm `/admin/products` renders rows through the full proxy→FastAPI chain.
- [ ] 4.2 Confirm `JWT_SECRET` absent from `next build` client output (grep artifacts for the secret / stray `NEXT_PUBLIC_*`).

## Phase 5: Cleanup

- [ ] 5.1 Document new env vars + admin-user provisioning step in relevant README.
- [ ] 5.2 Full `pytest` + `npm test` run, confirm all green.
