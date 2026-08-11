# Apply Progress: Admin Panel Authentication

## Scope of this batch

PR1 of 3 (stacked-to-main): Phase 1 only — backend JWT verification (ES256/JWKS,
corrected from the original HS256 assumption) + `require_db_pool` DB guard +
`GET /admin/products` proof endpoint. Phase 0 (prerequisite, done by the
orchestrator) was already `[x]`. Phases 2–5 are untouched and remain `[ ]`.

Branch: `pr1-admin-jwt-backend` (off `main`, which has the archived
`products-postgres-adapter` backend).

## Completed Tasks (Phase 1 — all 12)

- [x] 1.1 RED `backend/tests/unit/shared/test_auth.py` — 8 negative cases + happy
      path + identical-body proof + 2 extra fail-closed-500 misconfig cases +
      1 issuer/audience-from-config triangulation case (13 tests total)
- [x] 1.2 GREEN `backend/src/gcell/shared/infrastructure/config.py` —
      `jwks_url()`, `jwt_issuer()`, `jwt_audience()` (NOT `jwt_secret()`)
- [x] 1.3 GREEN `backend/src/gcell/shared/infrastructure/auth.py` —
      `AdminIdentity`, `verify_admin_jwt` (PyJWT + `PyJWKClient`,
      `algorithms=["ES256"]`, require `exp/iss/aud/sub`)
- [x] 1.4 `pyjwt[crypto]>=2.10` added via `uv add` — `cryptography` was NOT
      already transitive, confirmed via `uv pip list` before/after; pulled in
      explicitly by the `[crypto]` extra
- [x] 1.5 RED `backend/tests/unit/shared/test_dependencies.py` —
      `require_db_pool` None-pool → 503
- [x] 1.6 GREEN `backend/src/gcell/shared/infrastructure/dependencies.py`
- [x] 1.7 RED `backend/tests/integration/api/test_admin.py` — 3 cases: bad
      token+pool=None→401 (order proof), valid token+pool=None→503, valid
      token+pool→200 via `list_all` spy
- [x] 1.8 GREEN `backend/src/gcell/api/admin.py` — router,
      `GET /admin/products`, `AdminProductResponse`/`AdminProductVariantResponse`
- [x] 1.9 Wired `backend/src/gcell/main.py` — `include_router(admin_router)`,
      refreshed lifespan comment
- [x] 1.10 `backend/.env.example` — added `SUPABASE_JWKS_URL`,
      `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` (NOT `JWT_SECRET`)
- [x] 1.11 Regression — `test_lifespan.py`/`test_health.py` confirmed 0-byte
      diff (`git diff --stat` empty) and green
- [x] 1.12 `asyncpg` in `BANNED_MODULES` — already present (added by
      `products-postgres-adapter`); confirmed no further change needed

## Files Changed

| File | Action | What Was Done |
|---|---|---|
| `backend/src/gcell/shared/infrastructure/config.py` | Modified | Added `jwks_url()`, `jwt_issuer()`, `jwt_audience()` (default `"authenticated"`) |
| `backend/src/gcell/shared/infrastructure/auth.py` | Created | `AdminIdentity`, `verify_admin_jwt`; lazily-constructed (`lru_cache`) module-wide `PyJWKClient` |
| `backend/src/gcell/shared/infrastructure/dependencies.py` | Created | `require_db_pool` — 503 when `app.state.db_pool` is `None` |
| `backend/src/gcell/api/admin.py` | Created | `/admin` router (router-level `Depends(verify_admin_jwt)`), `GET /admin/products`, response models |
| `backend/src/gcell/main.py` | Modified | `include_router(admin_router)`; refreshed lifespan comment |
| `backend/pyproject.toml` / `backend/uv.lock` | Modified | `pyjwt[crypto]>=2.10` |
| `backend/.env.example` | Modified | `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` |
| `backend/tests/unit/shared/admin_jwt_test_support.py` | Created | Pure JWT-forging helpers (`make_admin_token`, ES256 test keypairs, HS256-confusion forger) |
| `backend/tests/unit/shared/conftest.py` | Created | Autouse fixture: monkeypatches `PyJWKClient.get_signing_key_from_jwt`, seeds env vars |
| `backend/tests/unit/shared/test_auth.py` | Created | 13 tests for `verify_admin_jwt` |
| `backend/tests/unit/shared/test_dependencies.py` | Created | 2 tests for `require_db_pool` |
| `backend/tests/unit/shared/test_config.py` | Modified | +6 tests for `jwks_url`/`jwt_issuer`/`jwt_audience` |
| `backend/tests/integration/api/admin_jwt_integration_support.py` | Created | `make_valid_admin_token()` helper for integration tests |
| `backend/tests/integration/api/conftest.py` | Created | Autouse JWKS-stub fixture, mirrors the unit-test one |
| `backend/tests/integration/api/test_admin.py` | Created | 3 router-wiring tests (order proof, 503, 200-with-spy) |
| `openspec/changes/admin-panel-auth/tasks.md` | Modified | Phase 1 tasks marked `[x]` |

## TDD Cycle Evidence (Strict TDD Mode)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.2 | `test_config.py` | Unit | N/A (new fns) | Written (ImportError) | Passed 8/8 | 6 cases (set/unset × 3 fns + audience-default) | Clean |
| 1.1/1.3 | `test_auth.py` | Unit | N/A (new file) | Written (ModuleNotFoundError) | Passed 11/11 | +2 fail-closed-500 cases | Clean |
| 1.5/1.6 | `test_dependencies.py` | Unit | N/A (new file) | Written (ModuleNotFoundError) | Passed 2/2 | 2 cases (None/configured) | Clean |
| 1.7/1.8/1.9 | `test_admin.py` | Integration | N/A (new route) | Written (404≠401/503) | Passed 3/3 | 3 distinct scenarios (order, 503, 200) | Clean |

### Test Summary
- **Total tests written**: 24 new (13 auth + 2 dependencies + 3 admin integration + 6 config)
- **Total tests passing**: 78/78 (full backend suite; 20 pre-existing DB-integration tests skip without a live-shell `DB_URL`, unaffected by this batch)
- **Layers used**: Unit (17), Integration (3), Config-unit (6, but grouped above); regression (test_health.py, test_lifespan.py: unmodified, 0-byte diff, green)
- **Approval tests**: None — no refactoring tasks in this batch
- **Pure functions created**: `make_admin_token`, `_forge_hs256_confusion_token`, `_public_key_pem_bytes`, `jwks_url`/`jwt_issuer`/`jwt_audience`

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd backend && uv run pytest tests/unit/shared/test_auth.py tests/unit/shared/test_dependencies.py tests/integration/api/test_admin.py tests/integration/api/test_lifespan.py tests/integration/api/test_health.py -v` → **21 passed** |
| Runtime harness command/scenario and exact result | `fastapi[standard]`/`uvicorn` are NOT installed in this project (pre-existing gap, out of scope to add for PR1). Substituted with a raw `TestClient(app)` script (env vars pointed at the REAL local Supabase JWKS endpoint, zero monkeypatch) run via `uv run python -c "..."`: no-Authorization → `401 {"detail":"invalid_token"}`; garbage Bearer token (forces a genuine live HTTP call to `http://127.0.0.1:54321/auth/v1/.well-known/jwks.json`) → `401 {"detail":"invalid_token"}`; `/health` → `200 {"status":"ok"}`. Proves the real network/JWKS-fetch code path end-to-end, not just the mocked unit/integration suite. |
| Rollback boundary | Revert `backend/src/gcell/shared/infrastructure/auth.py`, `dependencies.py`, `backend/src/gcell/api/admin.py`, the one `include_router`/comment line + `admin_router` import in `main.py`, the `pyjwt[crypto]` line in `pyproject.toml`/`uv.lock`, the 3 new env lines in `.env.example`, and all 6 new/modified test files. `config.py`'s 3 new functions are additive (no existing function touched). |

## Diff Size (measured, `git diff --stat` with intent-to-add for new files)

16 files changed, 911 insertions(+), 7 deletions(-) — including `uv.lock` (148
lines, machine-generated, excluded from authored risk count per the review
guard). **Authored lines ≈ 763 insertions / 7 deletions**, well above the
nominal 400-line budget for a single PR, but this exact scope (all of Phase 1)
was already the pre-resolved "PR 1" work unit in `tasks.md`'s "Suggested Work
Units" table (`chain strategy: stacked-to-main`, `delivery strategy:
ask-on-risk`) — a security-critical JWT-verification slice with 8 mandatory
negative-path test cases plus keypair-forging test infrastructure inherently
needs this much test scaffolding. Not re-litigated here; reported for
transparency.

## Deviations from Design

1. **`_jwks_client` is lazily constructed (`@lru_cache`), not built at
   `auth.py` import time as design.md's literal pseudocode shows.**
   `PyJWKClient(None)` raises immediately (`PyJWKClientError: Invalid JWKS URI
   scheme`), so a module-level `PyJWKClient(jwks_url())` would crash on
   import whenever `SUPABASE_JWKS_URL` is unset — including for
   `test_health.py`/unrelated tests once `main.py` imports `admin.py` →
   `auth.py` transitively (task 1.9). Lazy construction preserves the
   design's intent (cache keys across requests, once built) while removing
   the import-time crash hazard. The existing `if not issuer or not
   jwks_url(): raise HTTPException(500, ...)` fail-closed guard (extended
   from design's `issuer`-only check to also cover `jwks_url`) still catches
   real misconfiguration at request time.
2. **Added an explicit `creds.scheme.lower() != "bearer"` check** in
   `verify_admin_jwt`. In a real request, FastAPI's `HTTPBearer(auto_error=False)`
   already filters non-Bearer schemes to `None` before the dependency ever
   runs, so design's pseudocode has no explicit scheme check. Task 1.1 lists
   "non-Bearer" as a required unit-test case exercised by calling
   `verify_admin_jwt` directly (bypassing `HTTPBearer`'s own filtering), so
   the function needs its own defense-in-depth check to be correctly testable
   in isolation and safe if ever called from a non-FastAPI-DI context.
3. **Rewrote both test-support helper modules under unique names**
   (`admin_jwt_test_support.py`, `admin_jwt_integration_support.py`) instead
   of the initially-drafted approach of exporting helpers from each
   directory's `conftest.py`. Both `tests/unit/shared/conftest.py` and
   `tests/integration/api/conftest.py` would otherwise be plain Python
   modules literally named `conftest`, and this repo's test tree has no
   `__init__.py` chain — pytest's default "prepend" import mode makes
   `from conftest import X` resolve to whichever `conftest.py` Python's
   `sys.modules` cache loaded FIRST, process-wide. This was caught by
   actually running `tasks.md`'s own documented focused test command (which
   runs files from both directories together) — it failed with
   `ImportError: cannot import name 'OTHER_PRIVATE_KEY' from 'conftest'`
   before the fix. Fixed by giving each helper module a name unique across
   the whole test tree.
4. Added 3 unit tests beyond the 8 negative cases + happy path literally
   listed in task 1.1: `test_all_rejection_reasons_share_an_identical_response_body`
   (proves the spec's "no oracle" requirement, not just individual 401
   statuses), `test_missing_issuer_config_fails_closed_with_500` /
   `test_missing_jwks_url_config_fails_closed_with_500` (design's own
   fail-closed-500 branch, otherwise untested), and
   `test_verify_admin_jwt_uses_configured_issuer_and_audience` (triangulates
   that `iss`/`aud` are read from config, not hardcoded to the test
   constants).

## Issues Found

None blocking. The `sys.modules` collision (deviation 3) was a real bug
caught mid-batch by actually executing the documented focused test command,
not by inspection — worth noting for future SDD batches that name
cross-directory test helpers `conftest.py` in a project without
`__init__.py` package markers.

## Remaining Tasks (out of scope for PR1)

- [ ] Phase 2: Frontend session/proxy infrastructure (PR 2)
- [ ] Phase 3: Login page, admin pages, API proxy route (PR 3)
- [ ] Phase 4: End-to-end verification
- [ ] Phase 5: Cleanup

## Status (PR1)

12/12 Phase 1 tasks complete. Ready for `sdd-verify` on this PR1 slice, then
PR2 (`sdd-apply` Phase 2) targets this branch per `stacked-to-main`.

## Batch 2 (PR2 — Frontend Session & Proxy Infrastructure)

**Scope**: Phase 2 (9 tasks). Branch `pr2-admin-session-proxy` off `main`
(post-PR1). No login page, no admin pages yet — infrastructure only.
**Mode**: Strict TDD.

### Continuity note

This batch's `sdd-apply` sub-agent session was interrupted mid-run (process
restart, not a task failure). On resume, the orchestrator found 143/144
frontend tests passing with substantial real progress already on disk
(`proxy.ts`, `proxy.test.ts`, `proxy-client.ts`+test, `lib/admin/{redirect,env}.ts`
+tests, `server.ts` append, `.env.example`) and one genuine RED failure in
the conformance test extension (task 2.8). Reviewed all pre-existing code by
hand (found high quality — e.g. `isSafeAdminPath` correctly rejects
`//evil.com`/backslash-authority tricks via WHATWG `URL` origin comparison,
not a naive string prefix check; `proxy-client.ts` correctly applies both
cookie writes AND `@supabase/ssr@0.12.4`'s cache-suppressing response
headers). The orchestrator then diagnosed and fixed the one remaining RED
test itself (see below) rather than re-launching a fresh apply agent, since
the fix was well-understood and narrowly scoped.

### Tasks 2.8/2.9 — the one real finding

RED test (task 2.8) asserted `/api/admin/products` resolves to
`runtime-caching.ts`'s `NetworkOnly` handler while the same file also
asserts byte-identity to its pre-change state — a genuine contradiction:
`isAdminOrMutatingRequest` only checked the `/admin` prefix, and
`/api/admin` is a different prefix, so it did NOT match.

**Rejected fix**: rename the route under `/admin/*` (e.g. `/admin/api/products`)
to avoid touching the pinned file. Rejected because `proxy.ts`'s own
`config.matcher: ["/admin/:path*"]` deliberately EXCLUDES `/api/admin/*` so
the JSON proxy route (built in PR3) can return its own `401` instead of an
HTML redirect-to-login — renaming would silently break that exclusion and
send unauthenticated JSON callers an HTML page instead.

**Applied fix** (task 2.9): added `ADMIN_API_PREFIX = "/api/admin"` and one
`url.pathname.startsWith(ADMIN_API_PREFIX)` check to `isAdminOrMutatingRequest`
in `runtime-caching.ts`, mirroring the file's own existing
`CATALOG_API_PREFIX`/`isCatalogApiRead` pattern from `public-catalog-screens`.
This is the ONE deliberate, documented edit to that file across the entire
`admin-panel-auth` change. Recomputed the conformance test's pinned SHA256
to match the new content; any further, undocumented edit still fails the
test. `design.md` and `tasks.md` corrected to stop claiming a blanket
"zero changes"/"byte-identical" for ALL admin routes — that claim is true
for the `(admin)` group's page routes, false for this one API route.

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Full suite result | `npm --prefix frontend test` → 22 test files, 144 tests, all passed |
| Lint | `npm --prefix frontend run lint` → clean |
| Build | `npm --prefix frontend run build` → succeeded; route table confirms `ƒ Proxy (Middleware)` registered (Next.js recognizes `proxy.ts`, independent confirmation of the file-convention rename) |
| Rollback boundary | Delete `frontend/src/proxy.ts`+test, `frontend/src/lib/supabase/proxy-client.ts`+test, `frontend/src/lib/admin/`; revert the appended `createSessionClient` export in `server.ts`, the `ADMIN_API_PREFIX` addition in `runtime-caching.ts`, and `.env.example` |

### Files Changed

| File | Action |
|---|---|
| `frontend/src/proxy.ts` | Created — Next 16 `proxy` convention, session refresh, `/admin/*` guard, `next=` param, `/admin/login` pass-through/redirect rules |
| `frontend/src/lib/supabase/proxy-client.ts` | Created — request/response cookie-pair factory, applies cookies AND cache-suppressing headers |
| `frontend/src/lib/supabase/server.ts` | Modified (append only) — `createSessionClient()`; the two existing read-only catalog factories are byte-untouched |
| `frontend/src/lib/admin/redirect.ts` | Created — `isSafeAdminPath()` open-redirect guard via WHATWG `URL` origin comparison |
| `frontend/src/lib/admin/env.ts` | Created — `getBackendUrl()`, defaults to `http://127.0.0.1:8000` (not `localhost`, avoiding Node's IPv6-first DNS resolution racing `uvicorn`'s IPv4 bind) |
| `frontend/src/lib/pwa/runtime-caching.ts` | Modified — the one deliberate `/api/admin` prefix extension (see above) |
| `frontend/src/lib/pwa/__tests__/catalog-route-conformance.test.ts` | Modified — extended for `/admin`, `/admin/login`, `/admin/products`, `/api/admin/products`; pinned SHA256 recomputed |
| `frontend/.env.example` | Modified — `BACKEND_URL` |
| `openspec/changes/admin-panel-auth/design.md`, `tasks.md` | Modified — corrected the runtime-caching.ts "zero changes" claim to be precise about which routes it covers |

### Deviations from Design

None beyond the runtime-caching.ts finding above, which the design itself
had gotten wrong (not a deviation from a correct design, a correction of
an incorrect one) — already fully documented above and in `design.md`.

### Issues Found

None beyond the one finding above (which was resolved, not left open).

### Remaining Tasks (out of scope for PR2)

- [ ] Phase 3: Login page, admin pages, API proxy route (PR 3)
- [ ] Phase 4: End-to-end verification
- [ ] Phase 5: Cleanup

### Status (PR2)

9/9 Phase 2 tasks complete. Ready for `sdd-verify` on this PR2 slice, or
for PR3 to branch from `pr2-admin-session-proxy` once this PR merges.

## Batch 3 (PR3 — Login Pages, API Proxy Route, E2E)

**Scope**: Phase 3 (6 tasks) + Phase 4 (2 tasks). Branch
`pr3-admin-login-pages` off `pr2-admin-session-proxy` (stacked-to-main).
Does not touch any PR1/PR2 file.
**Mode**: Strict TDD (RED test written and confirmed failing, via actual
`npm test` execution, before every production file).

### Completed Tasks

- [x] 3.1 RED `frontend/src/app/api/admin/products/__tests__/route.test.ts`
      — 4 tests (no-claims-401 + fetch-never-called, empty-claims-401,
      proxies-with-bearer-200, throw-502)
- [x] 3.2 GREEN `frontend/src/app/api/admin/products/route.ts` — matches
      design.md's pseudocode exactly
- [x] 3.3 GREEN login page — split `page.tsx` (Server Component) +
      `login-form.tsx` (client, `useActionState`) + `actions.ts`
      (`signInAction`) — 9 tests
- [x] 3.4 GREEN admin layout — `actions.ts` (`signOutAction`, 1 test) +
      `layout.tsx` (shell + logout form, 3 tests)
- [x] 3.5 GREEN `frontend/src/app/(admin)/admin/page.tsx` — landing,
      1 test
- [x] 3.6 GREEN `frontend/src/app/(admin)/admin/products/page.tsx` —
      2 tests; found and fixed a real design gap (cookie forwarding, see
      Deviations below)
- [x] 4.1 One true E2E against the live local stack — see below
- [x] 4.2 Client-bundle env-leak check — see below

### Files Changed

| File | Action | What Was Done |
|---|---|---|
| `frontend/src/app/api/admin/products/route.ts` | Created | `GET` proxy: `getClaims()` gate, `getSession()` for the opaque token, `fetch` to `${getBackendUrl()}/admin/products` with `Authorization: Bearer`, 401/502 handling |
| `frontend/src/app/api/admin/products/__tests__/route.test.ts` | Created | 4 tests, `createSessionClient`/`fetch` mocked |
| `frontend/src/app/(admin)/admin/login/page.tsx` | Created | Server Component: reads `next` searchParam (handles `string \| string[] \| undefined`), renders `LoginForm` |
| `frontend/src/app/(admin)/admin/login/page.test.tsx` | Created | 3 tests, `LoginForm` stubbed |
| `frontend/src/app/(admin)/admin/login/login-form.tsx` | Created | Client component, `useActionState(signInAction, ...)`, labeled email/password inputs, generic error `role="alert"`, hidden `next` field |
| `frontend/src/app/(admin)/admin/login/login-form.test.tsx` | Created | 2 tests, `signInAction` mocked |
| `frontend/src/app/(admin)/admin/login/actions.ts` | Created | `signInAction`: `createSessionClient()` → `signInWithPassword` → generic error on failure / `redirect(resolveRedirectTarget(next))` on success |
| `frontend/src/app/(admin)/admin/login/actions.test.ts` | Created | 4 tests incl. same-generic-message-for-both-failure-modes (no-oracle proof) |
| `frontend/src/app/(admin)/admin/layout.tsx` | Created | Shell: header, `/admin` + `/admin/products` links, logout `<form action={signOutAction}>` |
| `frontend/src/app/(admin)/admin/layout.test.tsx` | Created | 3 tests (children pass through, products link, submit invokes action) |
| `frontend/src/app/(admin)/admin/actions.ts` | Created | `signOutAction`: `signOut()` then `redirect("/admin/login")` |
| `frontend/src/app/(admin)/admin/actions.test.ts` | Created | 1 test, call-order proof (`signOut` before `redirect`) |
| `frontend/src/app/(admin)/admin/page.tsx` | Created | Landing page, links to `/admin/products` |
| `frontend/src/app/(admin)/admin/page.test.tsx` | Created | 1 test |
| `frontend/src/app/(admin)/admin/products/page.tsx` | Created | Server Component: forwards the incoming request's `cookie` header via `next/headers`, builds an absolute URL from `host`/`x-forwarded-proto`, fetches `/api/admin/products`, renders a product/variant table or an error state |
| `frontend/src/app/(admin)/admin/products/page.test.tsx` | Created | 2 tests, `next/headers` + `fetch` mocked |
| `openspec/changes/admin-panel-auth/tasks.md` | Modified | Phase 3 + Phase 4 tasks marked `[x]` with DONE notes |

### TDD Cycle Evidence (Strict TDD Mode)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 3.1/3.2 | `route.test.ts` | Unit (Route Handler) | N/A (new file) | Written (import error) | Passed 4/4 | 4 distinct cases (401 no-claims, 401 empty-claims, 200-with-bearer, 502-throw) | Clean |
| 3.3 (action) | `actions.test.ts` (login) | Unit | N/A (new file) | Written (import error) | Passed 4/4 | Wrong-password vs no-such-user same message; safe-`next` vs unsafe-`next` | Clean |
| 3.3 (form) | `login-form.test.tsx` | Component (RTL) | N/A (new file) | Written (import error) | Passed 2/2 | Renders + submit-with-error | Clean |
| 3.3 (page) | `page.test.tsx` (login) | Component (RTL) | N/A (new file) | Written (import error) | Passed 3/3 | string / absent / array `next` | Clean |
| 3.4 (action) | `actions.test.ts` (admin) | Unit | N/A (new file) | Written (import error) | Passed 1/1 | ➖ Single (call-order is the only behavior) | Clean |
| 3.4 (layout) | `layout.test.tsx` | Component (RTL) | N/A (new file) | Written (import error) | Passed 3/3 | children / link / submit | Clean |
| 3.5 | `page.test.tsx` (admin) | Component (RTL) | N/A (new file) | Written (import error) | Passed 1/1 | ➖ Single — purely structural per design's File Changes ("Landing") | Clean |
| 3.6 | `page.test.tsx` (products) | Component (RTL) | N/A (new file) | Written (import error) | Passed 2/2 | Success-with-rows vs failure-with-error-state | Clean |

Every RED test was executed via `npm test -- <file>` and confirmed to fail
with an import-resolution error (production file did not exist yet) before
its GREEN implementation was written — not assumed.

### Test Summary

- **Total tests written this batch**: 20 (4 route + 4 login-actions + 2
  login-form + 3 login-page + 1 signout-action + 3 layout + 1 admin-landing
  + 2 products-page)
- **Full frontend suite**: `npm test` (no filter) → **164/164 passing**
  (144 from PR1+PR2 baseline + 20 new; zero regressions)
- **Layers used**: Unit (10: route handler + 2× server actions), Component/RTL (10: login-form, login-page, layout, admin-landing, products-page)
- **Approval tests**: None — no refactoring tasks in this batch
- **Pure functions created**: `resolveRedirectTarget` (login actions),
  `resolveNextParam` (login page), `fetchAdminProducts`/table-row mapping
  (products page)

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd frontend && npm test -- route.test.ts` → 16 passed (12 pre-existing `api/catalog/route.test.ts` + 4 new `api/admin/products/route.test.ts`); each new file's own focused run also captured individually above (all green) |
| Runtime harness command/scenario and exact result | See "One True E2E" below — full live-stack chain, not a substitute |
| Rollback boundary | Delete `frontend/src/app/api/admin/products/`, `frontend/src/app/(admin)/admin/**`; revert the `tasks.md` `[x]` marks for Phase 3/4. Zero PR1/PR2 files touched. |

### One True E2E (Task 4.1)

**Approach used**: (a) from the prompt's options — logged in as a **newly
provisioned** admin test user (`e2e-admin@gcell.local` /
`E2ETestPass123!`, created via `POST /auth/v1/signup` against the live
local Supabase Auth, same mechanism as `design.md`'s Prerequisite
section), because the original `admin@gcell.local` password was
unavailable after context compaction and the prompt explicitly
authorized this workaround.

**Live stack used**:
- Local Supabase (already running): Auth at `http://127.0.0.1:54321`,
  Postgres at `127.0.0.1:54322` (confirmed 3 real products / 5 variants
  present via a direct `asyncpg` query)
- FastAPI backend: started via `uv run --with uvicorn uvicorn
  gcell.main:app --app-dir src --host 127.0.0.1 --port 8000` — `uvicorn`
  is NOT a declared dependency (same pre-existing gap PR1 documented), so
  `--with uvicorn` resolves it into an ephemeral run-only environment
  without touching `pyproject.toml`/`uv.lock`. `DB_URL`,
  `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER` set inline.
- Next.js dev server: `npm run dev -- --port 3100` with
  `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`,
  `BACKEND_URL=http://127.0.0.1:8000` set inline.

**Steps executed and results** (via `curl`, not Playwright — none exists
in this repo, per design.md's own Testing Strategy):

1. `GET /admin/products` with no session cookie → **`307` to
   `/admin/login?next=%2Fadmin%2Fproducts`** (proxy gate + return-URL
   preservation, confirmed).
2. Fetched `/admin/login`, extracted Next 16's real progressive-
   enhancement Server Action hidden fields
   (`$ACTION_ID_...`/`$ACTION_REF_2`/`$ACTION_2:0`/`$ACTION_2:1`/
   `$ACTION_KEY`) from the rendered HTML, then `POST`ed a genuine
   `multipart/form-data` submission with `email`/`password` — this
   drives the REAL `signInAction` code path exactly as a JS-disabled
   browser would (not a shortcut around the form). Result: **`303 See
   Other`**, `Location: /admin` (safe default since `next=""`), and a
   real `Set-Cookie: sb-127-auth-token=...` carrying a genuine
   ES256-signed Supabase session.
3. `GET /admin/products` WITH that cookie → **`200`**, HTML contains 5
   real `<tr>` rows (`Funda iPhone 15` × 2 variants, `Funda Galaxy S24` ×
   2 variants, `Funda atómica` × 1 variant) with real name/model/color/
   price/cost values pulled from Postgres — proving the full chain:
   browser cookie → `proxy.ts` allow → RSC → cookie-forwarded `fetch` →
   `/api/admin/products` → `getClaims`/`getSession` →
   `Authorization: Bearer` → FastAPI `verify_admin_jwt` (real JWKS fetch
   against the live Auth instance, ES256) → `require_db_pool` →
   `PostgresProductRepository.list_all()` → real rows → rendered table.

**Result**: PASS — the entire login → `/admin` → `/admin/products`
chain works end-to-end against the live stack, both the unauthenticated
(redirect) and authenticated (render rows) branches confirmed.

Both servers were stopped after the check (`Stop-Process`); confirmed
`000`/connection-refused on both ports afterward.

### Env-Leak Check (Task 4.2)

`npm run build` (webpack, read-only — `next.config.ts` untouched) with
`SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, and `BACKEND_URL` deliberately
set in the build environment, to prove they do NOT leak even when
present.

- `grep -rl "SUPABASE_JWKS_URL\|BACKEND_URL\|127.0.0.1:8000\|jwks.json" .next/static` → **no matches** (exit 1)
- `grep -rn "NEXT_PUBLIC_.*(BACKEND_URL|JWKS|JWT_ISSUER|JWT_AUDIENCE)" frontend/src` → **no matches**
- Build succeeded; route table confirms `/admin`, `/admin/login`,
  `/admin/products`, `/api/admin/products` all present, `ƒ Proxy
  (Middleware)` registered. Noted (not a leak, informational):
  `/admin` (the landing page) is prerendered `○ Static` since it has no
  per-request data dependency — harmless, `proxy.ts` still gates it at
  request time regardless of static optimization.

**Result**: PASS.

### Deviations from Design

1. **`frontend/src/app/(admin)/admin/products/page.tsx` — cookie
   forwarding, a real gap in design.md, found and fixed, not silently
   patched.** design.md's Data Flow diagram says the RSC does a "fetch
   same-origin" to the proxy route but never states that a server-side
   `fetch()` inside a Server Component does NOT automatically carry the
   visiting browser's cookies (unlike a browser's own `fetch`, this is a
   separate outbound HTTP request from the Node process). Without
   forwarding the `cookie` header by hand, `createSessionClient()` inside
   `/api/admin/products/route.ts` would see no session on every request
   and the page would always render the error state — even for a
   genuinely authenticated admin. Fixed by reading the incoming request's
   `cookie` header via `next/headers`'s `headers()` and forwarding it
   explicitly, plus building an absolute URL from `host`/
   `x-forwarded-proto` (server-side `fetch` has no implicit base URL).
   Both the RED test (`page.test.tsx`, asserts the exact forwarded
   `cookie` header) and the live E2E check (4.1) prove this is a real,
   previously-invisible bug, not a theoretical one — the E2E would have
   returned the error state on step 3 above if this had been skipped.
2. No other deviations — `route.ts`, `actions.ts` (login and admin),
   `login-form.tsx`, `layout.tsx`, and the landing page all match
   design.md's stated contracts and File Changes table exactly.
3. **E2E driven via raw `curl` replicating Next 16's real progressive-
   enhancement Server Action wire format, not a simplified shortcut.**
   Considered and rejected: authenticating directly against the Supabase
   Auth REST API and manually constructing a session cookie (would prove
   the proxy→backend chain but NOT that `signInAction`/the login FORM
   itself works). Instead, extracted the actual hidden
   `$ACTION_ID_...`/`$ACTION_REF_2`/`$ACTION_KEY` fields Next embeds in
   the rendered login page HTML and submitted them exactly as a
   JS-disabled browser would — this exercises the real `signInAction`
   Server Action end-to-end, including its own internal
   `signInWithPassword` call and `redirect()`, not a bypass of it.

### Issues Found

None blocking beyond the one design gap in Deviation 1 above (found and
resolved within this batch, not left open).

### Remaining Tasks (out of scope for PR3)

- [ ] Phase 5: Cleanup (README documentation, full combined `pytest` +
      `npm test` run) — deliberately out of scope per the prompt's Phase
      5 exclusion

### Status (PR3)

8/8 Phase 3 + Phase 4 tasks complete. Diff size this batch: 16 files
changed, 983 insertions (production + test code) — plus 8/8 line changes
in `tasks.md` documentation. Well above the nominal 400-line budget, as
forecast in `tasks.md`'s Review Workload Forecast (`400-line budget risk:
High`, `Chained PRs recommended: Yes`) — this was the pre-resolved "PR 3"
work unit (`chain strategy: stacked-to-main`, `delivery strategy:
ask-on-risk`), not a scope overrun. Ready for `sdd-verify` on this PR3
slice. Only Phase 5 (cleanup/documentation) remains for the whole
`admin-panel-auth` change.
