# Delta for Admin API Access

## MODIFIED Requirements

### Requirement: Product Read And Write Endpoints

The `/admin` router MUST expose `GET /admin/products` (unchanged, backed by
`ProductRepository.list_all`) and MUST now also expose `POST
/admin/products` (create), `PATCH /admin/products/{id}` (update), `DELETE
/admin/products/{id}` (soft-delete a product), and `DELETE
/admin/products/{id}/variants/{variant_id}` (soft-delete a single variant).
Every write route MUST be gated by the same router-level `Depends
(verify_admin_jwt)` dependency as `GET /admin/products`, with no separate or
weaker verification path, and MUST follow the same
JWT-checked-before-DB-pool-checked-before-handler ordering already
established for GET. This requirement SUPERSEDES the prior constraint that
the router "MUST NOT expose any create, update, or delete admin endpoint in
this change" — that constraint was scoped to the `admin-panel-auth` change
only and no longer applies.
(Previously: "Read-Only Product Proof Endpoint" — router MUST expose only
`GET /admin/products` and MUST NOT expose any create, update, or delete
admin endpoint)

#### Scenario: Authenticated GET request returns product data

- GIVEN a request to `GET /admin/products` passes JWT verification
- WHEN the route handler executes
- THEN it MUST call `ProductRepository.list_all` and return its result
- AND the response MUST NOT mutate any product or stock data

#### Scenario: Unauthenticated GET never reaches the repository

- GIVEN a request to `GET /admin/products` fails any one of the four JWT
  checks
- WHEN the dependency short-circuits the request
- THEN `ProductRepository.list_all` MUST NOT be called

#### Scenario: Authenticated POST creates a product

- GIVEN a request to `POST /admin/products` carries a valid admin JWT and a
  valid body
- WHEN the route handler executes
- THEN it MUST invoke the create-capable repository operation and return
  the created product, including its server-derived `slug`

#### Scenario: Authenticated PATCH and DELETE reach their handlers

- GIVEN a request to `PATCH /admin/products/{id}` or `DELETE
  /admin/products/{id}` carries a valid admin JWT
- WHEN the route handler executes
- THEN it MUST invoke the corresponding `update` or `soft_delete`
  repository operation

#### Scenario: Unauthenticated write request is rejected before the DB pool guard or handler

- GIVEN a request to `POST /admin/products`, `PATCH /admin/products/{id}`,
  or either `DELETE` route with no valid admin JWT
- WHEN the request reaches the `/admin` router
- THEN the router-level JWT dependency MUST reject it with `401
  Unauthorized`
- AND the request MUST NOT reach the `require_db_pool` guard or the
  repository, so a DB outage can never surface as a `503` in place of the
  `401`

#### Scenario: Authenticated write request with an unavailable DB pool fails with 503

- GIVEN a request to a write endpoint passes JWT verification
- AND the connection pool is unavailable
- WHEN the request reaches the per-route `require_db_pool` dependency
- THEN the request MUST be rejected with `503 Service Unavailable`
- AND the repository MUST NOT be invoked
