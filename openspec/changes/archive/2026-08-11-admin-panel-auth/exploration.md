# Exploration: admin-panel-auth

Building the admin panel (protected UI + backend write endpoints) with authentication.

## Current State

**Frontend**: No `(admin)` route group and no `frontend/src/middleware.ts` exist (confirmed via glob — zero matches). No auth mechanism anywhere. `frontend/src/lib/supabase/server.ts` has two factories, both anon-key/read-only, built for the public catalog: `createAnonCatalogClient()` (`getAll: () => []`, `setAll: () => {}`) and `createRequestCatalogClient()` (reads cookies via `store.getAll()` but `setAll` is a no-op with a comment "revisit once authenticated routes land"). Neither can persist a Supabase Auth session — a new session-writing client factory (real `setAll`) is required. `frontend/package.json` has `@supabase/ssr@^0.12.4` but no `@supabase/supabase-js` and no JWT/jose library; no `NEXT_PUBLIC_BACKEND_URL`-style var exists anywhere.

**Backend**: `backend/src/gcell/main.py` confirmed — only `/health` is registered. `backend/pyproject.toml` deps are only `asyncpg` + `fastapi` — no JWT library. `app.state.db_pool` is published in the lifespan specifically so "the admin+auth change adds one `Depends` provider and nothing else" (design.md, `products-postgres-adapter`), which also flags that the current warn-and-continue behavior when `DB_URL` is unset must become fail-fast/503 once a route consumes the pool — unresolved today.

**RLS reality** (`supabase/migrations/20260810000458_public_catalog_rls.sql`, confirmed by read): base tables have RLS enabled with zero policies and zero `anon`/`authenticated` grants; only `catalog_*` views are granted to `anon`/`authenticated`; only `service_role` has base-table grants. `products-postgres-adapter`'s design.md states outright: "the DSN is a superuser connection that bypasses RLS by design (**authorization lands with the admin route layer**)" — this change is where that authz is meant to land.

**Supabase Auth config** (`supabase/config.toml`, confirmed by read): `enabled = true`, `site_url = "http://127.0.0.1:3000"`, `jwt_expiry = 3600`, no `signing_keys_path` (HS256 shared-secret `JWT_SECRET`), and critically `[auth.email] enable_confirmations = false` — email confirmation is off locally, so Mailpit isn't actually required for a working login flow (only for password-reset emails).

## Affected Areas

- `frontend/src/middleware.ts` — new file, `@supabase/ssr` session-refresh + route-protection pattern.
- `frontend/src/app/(admin)/**` — new route group.
- `frontend/src/lib/supabase/` — new session-aware client factory (existing two stay unchanged, read-only, catalog-only).
- `backend/src/gcell/main.py` — register `/admin` router; resolve `db_pool is None` tolerance.
- `backend/src/gcell/shared/infrastructure/` — new JWT-verification `Depends`.
- `backend/pyproject.toml` — add a JWT library (none exists today).
- `backend/src/gcell/products/application/register_product.py`, `backend/src/gcell/stock/application/register_stocked_product.py` — consumed as-is by the new composition root, no changes needed.
- No `CORSMiddleware` exists anywhere in the backend today (confirmed via repo-wide grep).

## Approaches

### Auth mechanism

1. **Supabase Auth email/password + `@supabase/ssr` middleware** — Pros: reuses already-running local Auth, `@supabase/ssr` already a dep, confirmations already disabled so the flow is simple for one user. Cons: pulls in GoTrue's full surface for one hardcoded user; JWT verification is new backend code that must be exactly right. Effort: Medium.
2. **Local-only shared-secret / custom session cookie** — Pros: fewer moving parts nominally. Cons: reinvents secure session handling (expiry, rotation, secure flags) that GoTrue already solves; discards the already-running Auth service; worse risk profile in practice. Effort: Medium (deceptively — not actually less work).

Recommendation: Approach 1.

### Frontend->backend call shape

1. **Direct browser -> FastAPI cross-origin fetch** with `Authorization: Bearer` — needs `CORSMiddleware`, exposes the raw token to client JS. Effort: Low-Medium.
2. **Next.js Route Handlers as server-to-server proxy** — no CORS needed, token never touches client JS, matches the existing `api/catalog/route.ts` precedent. Effort: Low-Medium.

Recommendation: Approach 2.

### Scope

1. **Minimal** — auth mechanism + one trivial protected endpoint (e.g. proxied `GET /admin/products`) to prove the chain end-to-end. Effort: Low-Medium.
2. **Medium** — Minimal + product list/create UI wired to `POST/GET /admin/products`. Effort: Medium-High; realistic risk of exceeding the 400-line PR budget.
3. **Full** — Medium + stock adjustment/editing UI; also unblocked by the still-deferred `StockLevelReader` bulk-read need flagged in `products-postgres-adapter`'s design.md. Effort: High.

Recommendation: **Minimal** — isolates the security-critical auth work from UI/form risk and fits the review budget; Medium becomes a natural follow-up change.

## Recommendation

Supabase Auth email/password, `@supabase/ssr` middleware for route protection with a new session-writing client factory, Route-Handler server-to-server proxying to FastAPI (avoids CORS entirely), a FastAPI `Depends` JWT-verification dependency on an `/admin` router prefix (checking signature/`exp`/`iss`/`aud`), and Minimal scope for this change.

## Risks

- JWT verification must check signature (HS256/`JWT_SECRET`), `exp`, `iss`, and `aud` — any omission is a real auth bypass.
- No JWT library exists in `backend/pyproject.toml` yet — must add one (`PyJWT` or `python-jose`).
- Middleware cookie adapter must follow the same verified `getAll`/`setAll` shape already established in `public-catalog-screens`, but now with a real `setAll` write-back (unlike the two existing no-op factories).
- `db_pool is None` tolerance in `main.py` is explicitly flagged as unsafe once a route consumes it — must be resolved in this change.
- No CORS middleware exists today; recommend the Route-Handler-proxy approach specifically to avoid needing it and to keep `JWT_SECRET` server-side only, never `NEXT_PUBLIC_*`.
- Creating the single admin user is a manual one-time step (Supabase Studio/CLI) outside this change's automated scope — call this out explicitly in the proposal.
- Confirmed no `authenticated`-role path to base tables via PostgREST exists; all admin writes must go through FastAPI's superuser `DB_URL` connection, consistent with `products-postgres-adapter`'s design intent.

## Ready for Proposal

Yes.
