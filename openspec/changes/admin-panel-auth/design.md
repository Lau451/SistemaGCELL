# Design: Admin Panel Authentication

## Technical Approach

Three layers, one trust boundary. (1) `frontend/src/proxy.ts` does an *optimistic* session refresh + redirect for `/admin/*`. (2) Route Handlers under `/api/admin/*` read the session server-side and forward the raw `access_token` as `Authorization: Bearer`. (3) **FastAPI is the only trust boundary**: `verify_admin_jwt` re-verifies signature/`exp`/`iss`/`aud` on every request. The frontend session read is a *routing* decision, never an authorization one — so a forged cookie buys nothing.

## Architecture Decisions

### Decision: `proxy.ts`, not `middleware.ts` (corrects proposal + spec text)

**Choice**: `frontend/src/proxy.ts` exporting `proxy(request)`.
**Verified**: `node_modules/next/dist/docs/01-app/03-api-reference/03-file-conventions/proxy.md:11` — "The `middleware` file convention is deprecated and has been renamed to `proxy`" (`v16.0.0`). Installed `next@16.3.0`. Proxy defaults to the **Node.js runtime**; setting `runtime` throws.
**Impact**: `admin-authentication` spec names `frontend/src/middleware.ts` literally. `sdd-tasks` MUST carry the rename; codemod `npx @next/codemod@canary middleware-to-proxy .` is unnecessary (greenfield file).

### Decision: admin routes live at `app/(admin)/admin/**`, not `app/(admin)/**`

**Choice**: `(admin)` is a layout-only group with a literal `admin` segment inside it.
**Rationale**: `initial-scaffolding/design.md:34` pins "**Admin URL contract**: the `(admin)` route group serves under `/admin/*`". A route group adds **no** URL segment, so the proposal's `app/(admin)/login/page.tsx` would serve `/login` — which does **not** match `isAdminOrMutatingRequest` in `runtime-caching.ts:42` and would fall through to Serwist's `defaultCache`, caching a login page in a shared cache. `/admin/login` is `NetworkOnly` by matcher rule #1 with **zero changes** to `runtime-caching.ts` (verified: `url.pathname.startsWith("/admin/")`).

### Decision: PyJWT, not python-jose — CORRECTED to ES256/JWKS, not HS256/shared-secret

**This design originally assumed HS256 with the shared `JWT_SECRET`. That assumption was proven wrong by the orchestrator before `sdd-apply` started**, per this doc's own "Open Questions" mandate to decode a real local token first. A real token was minted via `POST /auth/v1/signup` against the running local Supabase Auth (see the Prerequisite section below) and decoded:

- Header: `{"alg":"ES256","kid":"b81269f1-...","typ":"JWT"}` — **ES256 (asymmetric EC), not HS256**.
- Payload: `iss: "http://127.0.0.1:54321/auth/v1"`, `aud: "authenticated"` — both match the original assumption exactly, only `alg` was wrong.
- `GET /auth/v1/.well-known/jwks.json` (confirmed reachable, no auth beyond the anon `apikey` header) returns the matching public key by `kid`: `{"alg":"ES256","kty":"EC","crv":"P-256","kid":"b81269f1-...","x":"...","y":"..."}`.

This is the modern Supabase default (per-project asymmetric signing keys), not a misconfiguration to "fix" — the local stack genuinely does not use the legacy shared `JWT_SECRET` for signing. Verification must fetch the JWKS and verify with the matching public key, not a shared secret.

| Option | Tradeoff | Decision |
|---|---|---|
| `pyjwt` + `PyJWKClient` | `PyJWKClient(jwks_url).get_signing_key_from_jwt(token)` fetches/caches the JWKS and resolves the correct key by the token's `kid` automatically; typed exception hierarchy (`ExpiredSignatureError`, `InvalidIssuerError`, `InvalidAudienceError`, `InvalidSignatureError`, `PyJWKClientError`); `options={"require": [...]}` enforces claim presence; `algorithms=["ES256"]` still blocks `alg=none`/algorithm-confusion | **Chosen** (`pyjwt>=2.10`) |
| `python-jose` | Adds JWE surface never used; historic algorithm-confusion + JWE DoS CVEs; needs a crypto backend extra | Rejected |
| Hardcode the public key (skip JWKS fetch) | Avoids one HTTP call per verification (mitigated by `PyJWKClient`'s built-in cache); but silently breaks on any future key rotation with no clear failure signal | Rejected |

PyJWT's `PyJWKClient` is the correct, well-supported pattern for this — not exotic. The dependency choice (PyJWT over python-jose) still stands; only the signing-key acquisition and `algorithms=` allowlist change.

### Decision: per-request `503` dependency guard, not startup abort

**Rationale**: `tests/integration/api/test_lifespan.py:15` asserts `app.state.db_pool is None` when `DB_URL` is unset, inside a live `TestClient` context. A startup abort would break that test *and* `test_health.py`. A `require_db_pool` dependency scoped to `/admin` routes leaves `lifespan`, `/health`, and both tests untouched; `main.py` changes by one `include_router` line plus a comment refresh.

### Decision: `getClaims()` for the gate, `getSession()` only to extract the token

`getSession()` is explicitly untrustworthy over cookies (`auth-js/GoTrueClient.d.ts:1413`). Proxy and Route Handler both call `getClaims()` first (server-validated); `getSession().access_token` is read only afterwards, purely as an opaque string to relay.

## Data Flow

```
Browser ─GET /admin/products──▶ proxy.ts  (Node runtime, matcher /admin/:path*)
                                  │ createProxyClient(req,res) → getClaims()
                                  ├─ no claims ─▶ 307 /admin/login?next=/admin/products
                                  └─ claims ────▶ res (refreshed cookies + no-store headers)
                                        ▼
                          (admin)/admin/products/page.tsx  [RSC]
                                        │ fetch same-origin
                                        ▼
                       app/api/admin/products/route.ts
                          getClaims() ──none──▶ 401 JSON   (backend NEVER called)
                          getSession().access_token
                                        │ Authorization: Bearer <jwt>
                                        ▼
                    FastAPI  /admin  Depends(verify_admin_jwt)   ← trust boundary
                             │ sig(ES256, JWKS pubkey by kid) + exp + iss + aud
                             └─▶ Depends(require_db_pool) ─None─▶ 503
                                        ▼
                             pool.acquire() → PostgresProductRepository.list_all()
```

## File Changes

| File | Action | Description |
|---|---|---|
| `frontend/src/proxy.ts` | Create | Session refresh + `/admin/*` guard + `next=` param |
| `frontend/src/lib/supabase/server.ts` | Modify | **Append** `createSessionClient()`; the two existing factories are byte-untouched |
| `frontend/src/lib/supabase/proxy-client.ts` | Create | `createProxyClient(req, res)` (request/response cookie pair) |
| `frontend/src/lib/admin/redirect.ts` | Create | `isSafeAdminPath()` open-redirect guard |
| `frontend/src/lib/admin/env.ts` | Create | `getBackendUrl()` — same `requireEnvVar` pattern as `lib/supabase/env.ts` |
| `frontend/src/app/(admin)/admin/layout.tsx` | Create | Admin shell + logout Server Action |
| `frontend/src/app/(admin)/admin/page.tsx` | Create | Landing (`/admin`) |
| `frontend/src/app/(admin)/admin/login/page.tsx` | Create | Login form + `signInAction` Server Action |
| `frontend/src/app/(admin)/admin/products/page.tsx` | Create | Proof page consuming the proxy route |
| `frontend/src/app/api/admin/products/route.ts` | Create | Server-to-server proxy |
| `backend/src/gcell/shared/infrastructure/config.py` | Modify | `jwks_url()`, `jwt_issuer()`, `jwt_audience()` (NOT `jwt_secret()` — corrected, see ES256/JWKS decision above) |
| `backend/src/gcell/shared/infrastructure/auth.py` | Create | `verify_admin_jwt`, `AdminIdentity`; module-level `PyJWKClient(jwks_url())` instance (cached across requests) |
| `backend/src/gcell/shared/infrastructure/dependencies.py` | Create | `require_db_pool` |
| `backend/src/gcell/api/admin.py` | Create | `/admin` router + `GET /admin/products` (follows the existing `api/health.py` router convention, not the proposal's guessed `products/infrastructure/` path) |
| `backend/src/gcell/main.py` | Modify | `include_router(admin_router)`; refresh the stale lifespan comment |
| `backend/pyproject.toml` / `uv.lock` | Modify | `pyjwt>=2.10` |
| `frontend/.env.example`, `backend/.env.example` | Modify/Create | `BACKEND_URL`, `SUPABASE_JWKS_URL` (NOT `JWT_SECRET` — corrected), `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` |

## Interfaces / Contracts

### Cookie adapter — **verified against installed `@supabase/ssr@0.12.4`**

`SetAllCookies` takes **two** arguments (`types.d.ts:23`): `(cookies, headers: Record<string,string>)`. The second carries `Cache-Control: private, no-cache, no-store, must-revalidate, max-age=0`, `Expires: 0`, `Pragma: no-cache` and **must** be applied to the response, or a CDN can serve one user's session to another. Older two-arg-less examples are wrong for this version.

```ts
// lib/supabase/server.ts — APPEND ONLY
export async function createSessionClient() {
  const { url, anonKey } = getCatalogSupabaseEnv();
  const store = await cookies();                    // Next 16: async, awaited once
  return createServerClient(url, anonKey, {
    cookies: {
      getAll: () => store.getAll(),                 // adapter stays SYNC
      setAll: (cookiesToSet) => {
        try {
          for (const { name, value, options } of cookiesToSet)
            store.set(name, value, options);
        } catch {
          // Read-only store: called from an RSC. Safe to ignore — proxy.ts
          // already refreshed the cookies for this request.
        }
      },
    },
  });
}

// lib/supabase/proxy-client.ts
export function createProxyClient(request: NextRequest, response: NextResponse) {
  return createServerClient(url, anonKey, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (cookiesToSet, headers) => {
        for (const { name, value, options } of cookiesToSet) {
          request.cookies.set(name, value);          // downstream sees fresh
          response.cookies.set(name, value, options);
        }
        for (const [k, v] of Object.entries(headers)) response.headers.set(k, v);
      },
    },
  });
}
```

### `proxy.ts`

```ts
export const config = { matcher: ["/admin/:path*"] };
```

`/api/admin/*` is deliberately **excluded**: redirecting a JSON fetch to an HTML login page is a bug; the Route Handler returns `401` instead. `/admin/login` is inside the matcher (so an authenticated visitor gets bounced to `/admin`) but exempt from the unauthenticated redirect, or the redirect loops.

| Path | Claims | Result |
|---|---|---|
| `/admin/login` | none | pass through (render form) |
| `/admin/login` | valid | `307 → /admin` |
| `/admin/*` other | none | `307 → /admin/login?next=<pathname+search>` |
| `/admin/*` other | valid | pass through, response carries refreshed cookies + no-store headers |

**Open-redirect guard** (`isSafeAdminPath`): accept `next` only when it `=== "/admin"` or `startsWith("/admin/")` **and** does not start with `//` or `/\`. Anything else falls back to `/admin`. `signInAction` redirects to `isSafeAdminPath(next) ? next : "/admin"`.

### Login / logout

Server Components + Server Actions (not a `createBrowserClient`): the token is written by the server, so the browser never handles it — the proposal's stated posture. `signInAction` → `createSessionClient()` → `signInWithPassword({email,password})`; on `error`, re-render the form with a generic message (never distinguish "no such user" from "wrong password"); on success, `redirect(safeNext)`. `signOutAction` → `signOut()` → `redirect("/admin/login")`.

### `GET /api/admin/products`

```ts
export async function GET() {
  const supabase = await createSessionClient();
  const { data, error } = await supabase.auth.getClaims();
  if (error || !data?.claims)
    return NextResponse.json({ error: "unauthenticated" }, { status: 401 });   // backend NOT called

  const { data: { session } } = await supabase.auth.getSession();
  if (!session) return NextResponse.json({ error: "unauthenticated" }, { status: 401 });

  let upstream: Response;
  try {
    upstream = await fetch(`${getBackendUrl()}/admin/products`, {
      headers: { Authorization: `Bearer ${session.access_token}` },
      cache: "no-store",
    });
  } catch {
    return NextResponse.json({ error: "backend_unavailable" }, { status: 502 });
  }
  return NextResponse.json(await upstream.json(), {
    status: upstream.status,
    headers: { "Cache-Control": "private, no-store" },
  });
}
```

`BACKEND_URL` defaults to **`http://127.0.0.1:8000`**, not `localhost`. Node ≥18 resolves `localhost` verbatim and may pick `::1`, while `uvicorn` binds `127.0.0.1` by default → intermittent `ECONNREFUSED`. `BACKEND_URL` is server-only; adding a `NEXT_PUBLIC_` twin would defeat the whole proxy shape.

### `verify_admin_jwt` — CORRECTED to ES256/JWKS (see decision above)

```python
_bearer = HTTPBearer(auto_error=False)
_jwks_client = PyJWKClient(jwks_url())          # module-level: caches keys across requests

def verify_admin_jwt(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AdminIdentity:
    issuer, audience = jwt_issuer(), jwt_audience()
    if not issuer:
        raise HTTPException(500, "auth_misconfigured")     # fail closed, never 200
    if creds is None:
        raise _unauthorized()
    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(creds.credentials)
        claims = jwt.decode(
            creds.credentials,
            key=signing_key.key,
            algorithms=["ES256"],                          # blocks alg=none / HS256-confusion
            issuer=issuer,                                 # check 3
            audience=audience,                             # check 4
            options={"require": ["exp", "iss", "aud", "sub"],
                     "verify_signature": True,             # check 1
                     "verify_exp": True},                  # check 2
            leeway=0,
        )
    except (jwt.InvalidTokenError, PyJWKClientError):      # parent of every failure mode
        raise _unauthorized()                              # one generic body — never leak which check failed
    return AdminIdentity(subject=claims["sub"], email=claims.get("email"))
```

`_unauthorized()` → `HTTPException(401, "invalid_token", headers={"WWW-Authenticate": "Bearer"})`.

**Issuer/audience/algorithm values — CONFIRMED against a real token, not assumed.** The orchestrator provisioned the one admin user via `POST /auth/v1/signup` and decoded the resulting access token before `sdd-apply` started: header `{"alg":"ES256","kid":"b81269f1-..."}`, payload `iss: "http://127.0.0.1:54321/auth/v1"`, `aud: "authenticated"`. `iss`/`aud` matched this document's original assumption exactly; `alg` did not (was assumed HS256, is actually ES256) — corrected throughout this document. `GET /auth/v1/.well-known/jwks.json` (reachable with just the anon `apikey` header, no further auth) returns the public key matching the token's `kid`. `SUPABASE_JWKS_URL` (not `JWT_SECRET`), `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE` (default `"authenticated"`) are read from env.

### Router wiring

```python
router = APIRouter(prefix="/admin", tags=["admin"],
                   dependencies=[Depends(verify_admin_jwt)])

@router.get("/products")
async def list_admin_products(
    pool: Annotated[asyncpg.Pool, Depends(require_db_pool)],
) -> list[AdminProductResponse]:
    async with pool.acquire() as conn:
        products = await PostgresProductRepository(conn).list_all()
    return [AdminProductResponse.from_domain(p) for p in products]
```

Router-level dependencies run **before** path-operation dependencies, so an unauthenticated caller gets `401` and can never probe DB availability via `503`. `require_db_pool` reads `getattr(request.app.state, "db_pool", None)` and raises `HTTPException(503, "database_unavailable")`. Pydantic response models live in `api/`, never in `products/domain/` (the boundary test bans `pydantic` there).

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Unit (BE) | 4 checks × negative paths | **CORRECTED for ES256/JWKS** (was written against the wrong HS256 assumption): `conftest.py` generates its own throwaway ES256 keypair (`cryptography`'s `ec.generate_private_key(ec.SECP256R1())` — already a transitive dep via `pyjwt[crypto]`/`asyncpg`'s SSL support, confirm at apply time) and monkeypatches `PyJWKClient.get_signing_key_from_jwt` to return a `PyJWK`-wrapping the TEST public key, so `verify_admin_jwt` runs its real code path with zero network calls and zero live Auth dependency. `make_admin_token(private_key=TEST_KEY, iss=ISS, aud="authenticated", exp_delta=3600, sub=..., alg="ES256")`. Cases: no header, non-Bearer scheme, `exp_delta=-1`, wrong `iss`, wrong `aud`, signed with a *different* EC keypair (tampered — the real-world attack this guards against: a token signed with any key other than the one the JWKS `kid` names), missing `exp`, `alg="HS256"` using the TEST public key bytes as an HMAC secret (the classic asymmetric→symmetric algorithm-confusion attack — this is exactly why `algorithms=["ES256"]` must be an explicit allowlist, never inferred from the token's own header). **No live Auth service needed for any of these** — the monkeypatch replaces the JWKS fetch, not the verification logic. |
| Unit (BE) | happy path | Valid token → `AdminIdentity`; assert body is identical generic `invalid_token` across all failures (no oracle). |
| Integration (BE) | Router wiring | `TestClient`: bad token + `db_pool=None` → `401` (proves auth precedes pool); valid token + `db_pool=None` → `503`; valid token + real pool → `200` with `list_all()` rows. Repository call asserted absent via monkeypatched spy. |
| Regression (BE) | No collateral damage | `test_health.py` / `test_lifespan.py` run **unmodified** and stay green. |
| Unit (FE) | `isSafeAdminPath` | `//evil.com`, `/\evil.com`, `https://evil`, `/catalog`, `/adminx` → rejected; `/admin`, `/admin/products?x=1` → accepted. |
| Unit (FE) | Route Handler | Stubbed `createSessionClient` + spied `fetch`: no claims → `401` **and** `fetch` never called; claims → exactly one call with `Authorization: Bearer <token>`. |
| Conformance (FE) | SW matcher | Extend the existing `lib/pwa/__tests__/catalog-route-conformance.test.ts` style: `/admin`, `/admin/login`, `/admin/products`, `/api/admin/products` all resolve to the `NetworkOnly` entry; assert `runtime-caching.ts` is unmodified. |
| E2E | Full chain | **Exactly one** manual check against the live local stack (login → `/admin/products` renders rows). No Playwright exists (`initial-scaffolding`); this stays a documented apply-time verification, not a pinned-suite test. |

## Threat Matrix

| Boundary | Applicability | Design response |
|---|---|---|
| Documentation-like paths | N/A — no file-classification or execution-from-file logic ships | — |
| Git repository selection | N/A — no VCS invocation at runtime | — |
| Commit state | N/A | — |
| Push state | N/A | — |
| PR commands | N/A — no shell/subprocess/PR automation | — |

The matrix's shell/VCS rows do not apply. The real adversarial boundary is **HTTP path matching and token verification**, carried as RED tests above: (a) `/adminx` and `/admin-foo` must NOT be treated as admin by `isSafeAdminPath`; (b) a `next=` value pointing off-origin must be rejected; (c) `alg="none"` and HS256-algorithm-confusion tokens (signed using the public EC key bytes as an HMAC secret) must be rejected by the `algorithms=["ES256"]` allowlist; (d) `/api/admin/*` must return `401` JSON, never an HTML redirect.

## Migration / Rollout

No data migration. Additive except three in-place edits (`main.py`, `pyproject.toml`, appending one export to `server.ts`). Rollback = revert; the manually created Auth user stays and is inert.

**Prerequisite — admin user provisioning (blocking, manual, not automatable by this change) — DONE, by the orchestrator, before `sdd-apply` started.** No Supabase CLI subcommand creates users. Because `auth.enable_signup = true` and `auth.email.enable_confirmations = false` in `config.toml`, one call yields an immediately-confirmed user:

```bash
curl -X POST "http://127.0.0.1:54321/auth/v1/signup" \
  -H "apikey: <ANON_KEY from 'supabase status'>" -H "Content-Type: application/json" \
  -d '{"email":"admin@gcell.local","password":"<>=6 chars>"}'
```

Executed against the local stack: user `admin@gcell.local` now exists and is confirmed. `sdd-apply` does not need to repeat this step, only verify the user is still present if the local Supabase instance was reset since.

## Open Questions — RESOLVED

- [x] Spec text in `admin-authentication` said `frontend/src/middleware.ts`; Next 16 requires `proxy.ts`. **Fixed directly by the orchestrator** in `specs/admin-authentication/spec.md` (now says `proxy.ts`/`proxy()`/`/admin/login`) and re-synced to the Engram mirror, which `sdd-tasks` had independently flagged as stale.
- [x] `sdd-apply` MUST decode a real local token and confirm `alg`/`iss`/`aud`. **Done by the orchestrator, not deferred to `sdd-apply`**: `alg` was WRONG (assumed HS256, is actually **ES256** — the local stack uses per-project asymmetric signing keys, the modern Supabase default). `iss`/`aud` were both correct as assumed. This is the "escalate, not patch" scenario this document called out — handled by correcting the JWT-verification design (PyJWKClient/ES256 throughout this document) BEFORE any apply work started, not by silently proceeding with a verification scheme that would reject every real token.
