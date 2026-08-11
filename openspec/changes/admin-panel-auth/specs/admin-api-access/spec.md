# Admin API Access Specification

## Purpose

Protect the FastAPI `/admin` router with mandatory, fully-checked JWT
verification, expose exactly one read-only proof endpoint
(`GET /admin/products`), and guarantee the signing secret never reaches the
client.

## Requirements

### Requirement: JWT Verification Dependency On The Admin Router
Every route under the `/admin` router prefix MUST be gated by a FastAPI
`Depends` dependency that verifies, on every request, ALL FOUR of: (1) the
token signature using HS256 and the backend-only `JWT_SECRET`, (2) the
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
  invalidating the HS256 signature
- WHEN the request reaches the `/admin` router
- THEN the dependency MUST reject the request with `401 Unauthorized`

#### Scenario: Valid token on all four checks is accepted
- GIVEN a request bearing a JWT with a correct HS256 signature, unexpired
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

### Requirement: JWT Secret Is Backend-Only
`JWT_SECRET` MUST be read only from backend server-side environment
configuration and MUST NEVER be defined as, or exposed through, a
`NEXT_PUBLIC_*` environment variable or any value shipped in the frontend
client bundle.

#### Scenario: Secret absent from client bundle
- GIVEN the frontend build output
- WHEN environment variable usage is inspected
- THEN no `NEXT_PUBLIC_*` variable SHALL carry the `JWT_SECRET` value
- AND no client-side bundle SHALL contain the literal secret value

#### Scenario: Secret is available to the backend verification dependency
- GIVEN the FastAPI process environment
- WHEN the JWT verification dependency initializes
- THEN it MUST read `JWT_SECRET` from backend-only server environment
  configuration, not from any request or client-supplied value
