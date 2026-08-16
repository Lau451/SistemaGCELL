# Delta for Admin API Access

## ADDED Requirements

### Requirement: GET /admin/stock Endpoint

The `/admin` router MUST expose `GET /admin/stock`, gated by the same
router-level `Depends(verify_admin_jwt)` dependency as every other admin
route, with no separate or weaker verification path. It MUST compose
`ProductRepository.list_all()` with the existing bulk current-stock read
(`quantities_for_variants`) in exactly one bulk stock query, and return one
flat row per variant carrying its product's name and slug alongside the
variant's current quantity, via new list-only response model(s) — it MUST
NOT widen `AdminProductResponse` or any `AdminProductList*Response`. It MUST
accept two optional query parameters: `below` (integer; when present,
narrows results to rows whose quantity is less than or equal to `below`
(inclusive), with `below=0` accepted as a valid value meaning "out-of-stock
only", never clamped to `1` or treated as absent — a negative value clamps
to `0` rather than erroring) and `search` (free-text, case-insensitive
substring match against product name or variant color). Both parameters
MUST be clamped/normalized in application code, never rejected by FastAPI
`Query()` validators; when both are present they combine with AND. If the
bulk stock read fails, the route MUST propagate the failure to the
framework's default error response (no `_execute_or_raise` wrapping),
mirroring `GET /admin/products`.

#### Scenario: Unauthenticated request never reaches the repository

- GIVEN a `GET /admin/stock` request with no valid admin JWT
- WHEN the request reaches the `/admin` router
- THEN it MUST be rejected with `401 Unauthorized`
- AND neither `ProductRepository.list_all` nor the bulk stock read MUST be
  invoked

#### Scenario: Authenticated request returns one row per variant from one bulk query

- GIVEN a catalog with multiple products, each with one or more variants
- WHEN an authenticated admin requests `GET /admin/stock` with no query
  params
- THEN the response MUST contain exactly one row per variant
- AND each row MUST carry its product's name, its product's slug, and its
  current quantity
- AND exactly one bulk stock query MUST back the response, regardless of
  variant count

#### Scenario: below=0 is accepted and not clamped to 1

- GIVEN a request `GET /admin/stock?below=0`
- WHEN the route handler executes
- THEN it MUST treat `0` as the literal threshold, not substitute `1` or
  ignore the parameter

#### Scenario: Bulk stock read failure propagates to a 500, not a partial response

- GIVEN the bulk current-stock read raises an error
- WHEN an authenticated admin requests `GET /admin/stock`
- THEN the response MUST be the framework's default `500` error
- AND no row list, complete or partial, MUST be returned
