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

## Phase 0: Prerequisite (blocking, manual) — DONE by the orchestrator before apply

- [x] 0.1 Provision admin user: `POST http://127.0.0.1:54321/auth/v1/signup` (design.md curl). DONE — `admin@gcell.local` created and confirmed against the running local stack.
- [x] 0.2 Decode a real token for that user; confirm `alg`/`iss`/`aud`. DONE — **`alg` was WRONG** (assumed HS256, real value is **ES256**, per-project asymmetric key, confirmed via `GET /auth/v1/.well-known/jwks.json`). `iss` (`http://127.0.0.1:54321/auth/v1`) and `aud` (`authenticated`) matched the assumption exactly. `design.md` corrected throughout (PyJWKClient/ES256, not shared-secret/HS256) BEFORE this apply batch — `sdd-apply` must follow the corrected design, not the original HS256 text.

## Phase 1: Backend — JWT Verification & DB Guard (PR 1)

- [x] 1.1 RED `backend/tests/unit/shared/test_auth.py`: `conftest.py` generates a throwaway ES256 test keypair and monkeypatches `PyJWKClient.get_signing_key_from_jwt` to return the TEST public key (no live Auth service, no network call — see design.md's corrected Testing Strategy). `make_admin_token` factory; cases missing token, non-Bearer, expired, wrong `iss`, wrong `aud`, tampered signature (signed with a *different* EC keypair), missing `exp`, `alg="HS256"` using the test public key bytes as an HMAC secret (algorithm-confusion attack) — all 401, identical body. DONE — 13 tests (8 negative cases + happy path + identical-body proof + 2 extra fail-closed-500-misconfig cases + issuer/audience-from-config triangulation).
- [x] 1.2 GREEN `backend/src/gcell/shared/infrastructure/config.py`: add `jwks_url()`, `jwt_issuer()`, `jwt_audience()` (NOT `jwt_secret()`). DONE.
- [x] 1.3 GREEN `backend/src/gcell/shared/infrastructure/auth.py`: `AdminIdentity`, `verify_admin_jwt` (PyJWT + `PyJWKClient`, `algorithms=["ES256"]`, require `exp/iss/aud/sub`). DONE — lazily-constructed (`lru_cache`) module-wide `PyJWKClient`, not built at import time (see apply-progress deviation note).
- [x] 1.4 Add `pyjwt>=2.10` to `backend/pyproject.toml`; update `uv.lock`. Confirm the EC-keypair-generation dependency (`cryptography`, likely already transitive) is available for the test fixture. DONE — added as `pyjwt[crypto]>=2.10` via `uv add`; `cryptography` was NOT already transitive (confirmed via `uv pip list` before/after), pulled in explicitly by the `[crypto]` extra.
- [x] 1.5 RED `backend/tests/unit/shared/test_dependencies.py`: `require_db_pool` — `None` pool → 503. DONE.
- [x] 1.6 GREEN `backend/src/gcell/shared/infrastructure/dependencies.py`: `require_db_pool`. DONE.
- [x] 1.7 RED `backend/tests/integration/api/test_admin.py`: bad token+`pool=None`→401 (order proof); valid token+`pool=None`→503; valid token+pool→200 via `list_all` spy. DONE.
- [x] 1.8 GREEN `backend/src/gcell/api/admin.py`: router, `GET /admin/products`, response model. DONE.
- [x] 1.9 Wire `backend/src/gcell/main.py`: `include_router(admin_router)`; refresh lifespan comment. DONE.
- [x] 1.10 Add `SUPABASE_JWKS_URL` (NOT `JWT_SECRET`), `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` to `backend/.env.example`. DONE.
- [x] 1.11 Regression: run `test_lifespan.py`/`test_health.py` unmodified, confirm green. DONE — 0-byte diff on both files, both pass (`test_lifespan.py`'s real-DB test also confirms the local Postgres is reachable).
- [x] 1.12 Add literal `asyncpg` entry to `BANNED_MODULES` domain-boundary fixture. DONE — already present (added by `products-postgres-adapter`); confirmed no further change needed, per the task's own escape hatch.

## Phase 2: Frontend — Session & Proxy Infrastructure (PR 2)

- [x] 2.1 RED `frontend/src/lib/admin/__tests__/redirect.test.ts`: `isSafeAdminPath` rejects `//evil.com`, `/\evil.com`, `https://evil`, `/adminx`, `/catalog`; accepts `/admin`, `/admin/products?x=1`.
- [x] 2.2 GREEN `frontend/src/lib/admin/redirect.ts`: `isSafeAdminPath()`.
- [x] 2.3 GREEN `frontend/src/lib/admin/env.ts`: `getBackendUrl()` (default `http://127.0.0.1:8000`).
- [x] 2.4 GREEN (append only) `frontend/src/lib/supabase/server.ts`: add `createSessionClient()`; do not touch existing two factories.
- [x] 2.5 GREEN `frontend/src/lib/supabase/proxy-client.ts`: `createProxyClient(req, res)`, two-arg `setAll(cookies, headers)` applying cache-suppressing headers.
- [x] 2.6 GREEN `frontend/src/proxy.ts`: `export function proxy(request)`, `matcher: ["/admin/:path*"]`, `getClaims()` gate, `/admin/login` pass-through/redirect rules, `next=` param.
- [x] 2.7 Add `BACKEND_URL` to `frontend/.env.example`.
- [x] 2.8 RED extend `frontend/src/lib/pwa/__tests__/catalog-route-conformance.test.ts`: assert `/admin`, `/admin/login`, `/admin/products`, `/api/admin/products` resolve `NetworkOnly`; assert `runtime-caching.ts` matches a pinned hash. DONE — this RED test caught a real gap: `/api/admin/products` did NOT match the original `isAdminOrMutatingRequest` (`/api/admin` and `/admin` are different prefixes). Renaming the route under `/admin/*` was considered and rejected (it would break `proxy.ts`'s deliberate `/api/admin/*` exclusion, sending unauthenticated JSON callers an HTML redirect instead of `401`).
- [x] 2.9 GREEN: added `ADMIN_API_PREFIX = "/api/admin"` + one `startsWith` check to `isAdminOrMutatingRequest` in `runtime-caching.ts`, mirroring the file's existing `CATALOG_API_PREFIX`/`isCatalogApiRead` pattern. This is the ONE deliberate, documented edit to that file in this change; the conformance test's pinned SHA256 was recomputed to match. 144/144 tests pass.

## Phase 3: Login Page, Admin Pages, API Proxy Route (PR 3)

- [ ] 3.1 RED `frontend/src/app/api/admin/products/__tests__/route.test.ts`: no claims→401 JSON, `fetch` never called; claims→one call with `Authorization: Bearer`; network throw→502.
- [ ] 3.2 GREEN `frontend/src/app/api/admin/products/route.ts` per design.
- [ ] 3.3 GREEN `frontend/src/app/(admin)/admin/login/page.tsx`: form + `signInAction` (generic error only, safe-`next` redirect).
- [ ] 3.4 GREEN `frontend/src/app/(admin)/admin/layout.tsx`: shell + `signOutAction`.
- [ ] 3.5 GREEN `frontend/src/app/(admin)/admin/page.tsx`: landing.
- [ ] 3.6 GREEN `frontend/src/app/(admin)/admin/products/page.tsx`: consumes `/api/admin/products`.

## Phase 4: End-to-End Verification

- [ ] 4.1 One true E2E: log in with the provisioned admin user, confirm redirect into `/admin`, confirm `/admin/products` renders rows through the full proxy→FastAPI chain.
- [ ] 4.2 Confirm no backend-only env value (`SUPABASE_JWKS_URL`, `BACKEND_URL`) leaks into `next build`'s client output or a stray `NEXT_PUBLIC_*` var. Note: under the corrected ES256/JWKS design there is no shared signing secret to leak in the first place (verification only ever needs the PUBLIC key, openly served at `/auth/v1/.well-known/jwks.json` by design) — this check still guards against accidentally exposing `BACKEND_URL` or other internal config, not a forgeable secret.

## Phase 5: Cleanup

- [ ] 5.1 Document new env vars + admin-user provisioning step in relevant README.
- [ ] 5.2 Full `pytest` + `npm test` run, confirm all green.
