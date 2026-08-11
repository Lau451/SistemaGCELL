# Admin API Access Specification

## Purpose

Protect the FastAPI `/admin` router with mandatory, fully-checked JWT
verification, expose exactly one read-only proof endpoint
(`GET /admin/products`), and keep all backend-only auth configuration
server-side.

**Signing scheme note (corrected against a real token before apply):**
the local Supabase Auth instance signs tokens with **ES256** (asymmetric,
per-project key pair), not HS256/a shared secret as originally assumed —
verification uses the PUBLIC key served at
`/auth/v1/.well-known/jwks.json` via a `PyJWKClient`, never a secret the
backend must protect from disclosure. See `design.md`'s corrected
"Decision: PyJWT, not python-jose" section for the full finding.

## Requirements

### Requirement: JWT Verification Dependency On The Admin Router
Every route under the `/admin` router prefix MUST be gated by a FastAPI
`Depends` dependency that verifies, on every request, ALL FOUR of: (1) the
token signature using ES256 against the public key resolved from the
Supabase Auth JWKS endpoint (matched by the token's `kid`), (2) the
`exp` claim has not passed, (3) the `iss` claim matches the expected
issuer, and (4) the `aud` claim matches the expected audience. A request
MUST be rejected with `401 Unauthorized` unless all four checks pass.

#### Scenario: Missing token is rejected
- GIVEN a request to `GET /admin/products` with no `Authorization` header
- WHEN the request reaches the `/admin` router
- THEN the dependency MUST reject the request with `401 Unauthorized`
- AND `ProductRepository.list_all` MUST NOT be invoked

#### Scenario: Expired token is rejected
- GIVEN a request bearing a JWT whose `exp` claim is in the past
- WHEN the request reaches the `/admin` router
- THEN the dependency MUST reject the request with `401 Unauthorized`

#### Scenario: Wrong issuer is rejected
- GIVEN a request bearing a JWT with a valid signature and unexpired `exp`
  but an `iss` claim that does not match the expected issuer
- WHEN the request reaches the `/admin` router
- THEN the dependency MUST reject the request with `401 Unauthorized`

#### Scenario: Wrong audience is rejected
- GIVEN a request bearing a JWT with a valid signature, unexpired `exp`,
  and correct `iss`, but an `aud` claim that does not match the expected
  audience
- WHEN the request reaches the `/admin` router
- THEN the dependency MUST reject the request with `401 Unauthorized`

#### Scenario: Tampered signature is rejected
- GIVEN a request bearing a JWT whose payload was altered after signing,
  invalidating the ES256 signature
- WHEN the request reaches the `/admin` router
- THEN the dependency MUST reject the request with `401 Unauthorized`

#### Scenario: Algorithm-confusion signature is rejected
- GIVEN a request bearing a JWT signed with `alg: HS256` using the public
  EC key's bytes as an HMAC secret (the classic asymmetric-to-symmetric
  algorithm-confusion attack)
- WHEN the request reaches the `/admin` router
- THEN the dependency MUST reject the request with `401 Unauthorized`,
  because the verification allowlist accepts only `ES256`

#### Scenario: Valid token on all four checks is accepted
- GIVEN a request bearing a JWT with a correct ES256 signature, unexpired
  `exp`, correct `iss`, and correct `aud`
- WHEN the request reaches the `/admin` router
- THEN the dependency MUST allow the request through to the route handler

### Requirement: Read-Only Product Proof Endpoint
The `/admin` router MUST expose `GET /admin/products`, backed by the
existing `ProductRepository.list_all`, and MUST NOT expose any create,
update, or delete admin endpoint in this change.

#### Scenario: Authenticated request returns product data
- GIVEN a request to `GET /admin/products` passes JWT verification
- WHEN the route handler executes
- THEN it MUST call `ProductRepository.list_all` and return its result
- AND the response MUST NOT mutate any product or stock data

#### Scenario: Unauthenticated or invalid request never reaches the repository
- GIVEN a request to `GET /admin/products` fails any one of the four JWT
  checks
- WHEN the dependency short-circuits the request
- THEN `ProductRepository.list_all` MUST NOT be called

### Requirement: Backend Auth Configuration Stays Server-Side
`SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE`, and
`BACKEND_URL` MUST be read only from backend/server-side environment
configuration and MUST NEVER be defined as, or exposed through, a
`NEXT_PUBLIC_*` environment variable or any value shipped in the frontend
client bundle. This is an architectural boundary, not a secrecy
requirement — under ES256/JWKS verification, the JWKS URL and its public
key ARE meant to be publicly fetchable (that is the point of a JWKS
endpoint); the invariant being protected here is that the frontend never
performs its own JWT verification or bypasses the backend as the single
trust boundary, not that a value could be used to forge a token.

#### Scenario: Backend config absent from client bundle
- GIVEN the frontend build output
- WHEN environment variable usage is inspected
- THEN no `NEXT_PUBLIC_*` variable SHALL carry `SUPABASE_JWKS_URL`,
  `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE`, or `BACKEND_URL`
- AND no client-side bundle SHALL contain those literal values

#### Scenario: Configuration is available to the backend verification dependency
- GIVEN the FastAPI process environment
- WHEN the JWT verification dependency initializes
- THEN it MUST read `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`, and
  `SUPABASE_JWT_AUDIENCE` from backend-only server environment
  configuration, not from any request or client-supplied value
