# Delta for Admin API Access

## ADDED Requirements

### Requirement: Variant Stock Movement History Endpoint

The `/admin` router MUST expose `GET
/admin/products/{product_id}/variants/{variant_id}/stock/movements`,
gated by the same router-level `Depends(verify_admin_jwt)` dependency as
every other admin route, with no separate or weaker verification path. It
MUST accept optional query parameters `limit` (default 20, hard-capped at
100 — values above the cap MUST be clamped server-side, not rejected) and
`before_id` (optional exclusive keyset cursor), and MUST return `{
items: [...], next_before_id: <id or null> }` with `items` ordered `id
DESC` (newest first). A `variant_id` that does not exist, or that belongs
to a product other than `product_id`, MUST resolve to `404` via
`VariantNotFoundError`, never `403`. A variant with zero movements MUST
return `200` with an empty `items` array, not `404`.

#### Scenario: Unauthenticated history request is rejected before the repository

- GIVEN a `GET .../stock/movements` request with no valid admin JWT
- WHEN the request reaches the `/admin` router
- THEN it MUST be rejected with `401 Unauthorized`
- AND no `stock_movements` query MUST occur

#### Scenario: Foreign variant_id returns 404, never 403

- GIVEN product `A` and product `B` each have at least one variant
- WHEN an authenticated admin requests movement history scoped to product
  `A` with a `variant_id` belonging to product `B`
- THEN the response MUST be `404`
- AND it MUST NOT be `403`

#### Scenario: Empty history returns 200 with an empty list

- GIVEN a variant with zero recorded `stock_movements` rows
- WHEN an authenticated admin requests its movement history
- THEN the response MUST be `200` with `items: []` and
  `next_before_id: null`

#### Scenario: Limit above the hard cap is clamped

- GIVEN an authenticated request with `?limit=500`
- WHEN the route handler executes
- THEN it MUST clamp the effective limit to `100` rather than returning
  an error

#### Scenario: Cursor pagination follows next_before_id

- GIVEN a variant with more movements than `limit`
- WHEN an authenticated admin requests a first page, then a second page
  using the first page's `next_before_id` as `before_id`
- THEN every item on the second page MUST have an `id` strictly less
  than the first page's oldest item's `id`
