# Proposal: Admin Panel Authentication

## Intent

The `products`/`stock` domains are built and tested but have zero HTTP surface, and RLS grants `anon`/`authenticated` no base-table access — `products-postgres-adapter` deferred authorization to "the admin route layer". The single admin cannot reach any of that logic. This change builds that gate — login, protected routes, verified admin API access — isolated from product-management UI so the security-critical part gets undiluted review.

## Scope

### In Scope

- Supabase Auth email/password login page + logout, `(admin)` route group.
- New session-writing Supabase client factory in `frontend/src/lib/supabase/` (real `setAll` cookie write-back).
- `frontend/src/middleware.ts`: session refresh + `(admin)` protection, redirect unauthenticated → login.
- Next.js Route Handler proxy (server-to-server) attaching the access token to FastAPI calls.
- FastAPI `/admin` router + `Depends` JWT verification: signature (HS256, shared `JWT_SECRET`), `exp`, `iss`, `aud` — all four mandatory.
- One trivial protected endpoint, `GET /admin/products` via existing `ProductRepository.list_all`, proving the chain end-to-end (read-only).
- Convert `db_pool is None` tolerance in `main.py` to fail-fast/503.
- Add a pinned JWT library to `backend/pyproject.toml`.

### Out of Scope

- Product create/edit UI, stock adjustment UI, any admin CRUD workflow (follow-up change).
- Public catalog: `(public)` group, `catalog_*` views, `createAnonCatalogClient`, `createRequestCatalogClient` — unchanged.
- CORS middleware (proxy shape removes the need).
- Signup, password reset, multi-user roles, admin user provisioning.

## Capabilities

### New Capabilities

- `admin-authentication`: login/logout, session cookie lifecycle, `(admin)` route protection.
- `admin-api-access`: `/admin` router, JWT verification dependency, proxy call shape, proof endpoint.

### Modified Capabilities

- `platform-foundation`: DB pool lifecycle requirement changes from "pool not required for non-DB endpoints" to fail-fast/503 once `/admin` consumes it; adds `JWT_SECRET` as backend-only env.

## Approach

Supabase Auth (GoTrue) email/password via `@supabase/ssr` — reuses running local infra; `enable_confirmations = false` keeps the single-user flow simple. Browser never sees the token: middleware refreshes the session cookie, Route Handlers read it server-side and forward `Authorization` to FastAPI. FastAPI validates the JWT before any repository call.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `frontend/src/middleware.ts` | New | Session refresh + route guard |
| `frontend/src/app/(admin)/**` | New | Login page + one protected page |
| `frontend/src/lib/supabase/` | New file | Session-writing factory (additive) |
| `frontend/src/app/api/admin/**` | New | Server-to-server proxy |
| `backend/.../shared/infrastructure/` | New | JWT verify dependency |
| `backend/.../products/infrastructure/` | New | `/admin` router |
| `backend/src/gcell/main.py` | Modified | Register router, fail-fast pool |
| `backend/pyproject.toml` | Modified | JWT library |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Incomplete JWT checks = auth bypass | Med | All four checks spec'd as testable scenarios, incl. negative tests |
| `JWT_SECRET` leaked to client bundle | Low | Never `NEXT_PUBLIC_*`; enforced as success criterion |
| Cookie adapter shape wrong | Med | Reuse verified `getAll`/`setAll` pattern from `public-catalog-screens` |
| Fail-fast breaks `/health` tests | Med | Guard scoped to `/admin` dependency, not app boot for non-DB routes |
| Regressing the public catalog | Low | Existing factories untouched; change is purely additive |

## Rollback Plan

Revert the commits. Nothing destructive: no migrations, no schema edits, no public-catalog file touched. Only in-place edits are `main.py` (router + pool guard) and `pyproject.toml`; reverting restores warn-and-continue. The manually created Auth user stays — inert without the `/admin` router.

## Dependencies

- **Manual, one-time, outside this change's automated scope**: the single admin user must be created in Supabase Auth via Studio (`:54323`) or the CLI. It does not exist today; no task here will create it.
- Local Supabase stack running (Auth enabled, `jwt_expiry = 3600`); `JWT_SECRET` available to the backend process.

## Success Criteria

- [ ] Unauthenticated request to any `(admin)` route redirects to login.
- [ ] Valid credentials establish a session; the protected page renders product data fetched through the proxy.
- [ ] `GET /admin/products` rejects requests with a missing, expired, wrong-issuer, wrong-audience, or tampered-signature token.
- [ ] `JWT_SECRET` appears in no `NEXT_PUBLIC_*` variable and in no client bundle.
- [ ] Admin request with `DB_URL` unset returns 503, never a `None`-pool crash.
- [ ] Public catalog routes and their tests pass unchanged.
