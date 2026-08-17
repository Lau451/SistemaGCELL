# Delta for Admin API Access

## MODIFIED Requirements

### Requirement: Variant Stock Movement History Endpoint

The `/admin` router MUST expose `GET
/admin/products/{product_id}/variants/{variant_id}/stock/movements`,
gated by the same router-level `Depends(verify_admin_jwt)` dependency as
every other admin route, with no separate or weaker verification path. It
MUST accept optional query parameters `limit` (default 20, hard-capped at
100 — values above the cap MUST be clamped server-side, not rejected),
`before_id` (optional exclusive keyset cursor), `since` (optional,
inclusive lower bound on `created_at`), and `until` (optional, inclusive
of the entire selected day as an upper bound on `created_at`). `since` and
`until` MUST be validated and clamped in application code (the use case),
the same idiom as `limit`'s existing clamp, never via FastAPI's
declarative `Query()` validation. When `since` is later than `until`, the
request MUST be rejected with `422`, raised from application code. When
both `since` and `until` are omitted, the endpoint's behavior MUST be
identical to today's unfiltered response. The date-range predicate MUST
combine with, not replace, the existing `variant_id` + `before_id` keyset
predicate. The endpoint MUST return `{ items: [...], next_before_id: <id
or null> }` with `items` ordered `id DESC` (newest first). A `variant_id`
that does not exist, or that belongs to a product other than
`product_id`, MUST resolve to `404` via `VariantNotFoundError`, never
`403`. A variant with zero movements, or zero movements within the
requested range, MUST return `200` with an empty `items` array, not
`404`.
(Previously: accepted only `limit` and `before_id`; adds optional
`since`/`until` filtering, combined with the existing pagination
predicate, without changing `limit`/`before_id` behavior.)

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

#### Scenario: since and until filter created_at combined with the keyset predicate

- GIVEN a variant with movements both inside and outside a given date
  range, and more matching movements than `limit`
- WHEN an authenticated admin requests movement history with `?since=...`
  and `?until=...` set, then requests a second page using
  `next_before_id`
- THEN every returned item on both pages MUST have `created_at` within
  `[since, until]`
- AND the second page's items MUST still have `id` strictly less than the
  first page's oldest item's `id`

#### Scenario: Omitting since and until reproduces today's exact behavior

- GIVEN a variant with recorded movements
- WHEN an authenticated admin requests movement history with neither
  `since` nor `until` set
- THEN the response MUST be identical to the endpoint's behavior before
  `since`/`until` existed, filtered only by `variant_id` and `before_id`

#### Scenario: An inverted range is rejected with 422

- GIVEN an authenticated request with `?since=2026-08-20&until=2026-08-10`
- WHEN the use case validates the range
- THEN the response MUST be `422`
- AND the rejection MUST originate from application code, not FastAPI's
  declarative `Query()` validation

#### Scenario: until includes the entire selected day

- GIVEN a movement recorded at `23:59` on the date passed as `until`
- WHEN an authenticated admin requests movement history with that
  `until` value
- THEN that movement MUST be included in the response

#### Scenario: Zero movements within the requested range returns 200 with an empty list

- GIVEN a variant with recorded movements, none of which fall within the
  requested `since`/`until` range
- WHEN an authenticated admin requests movement history with that range
- THEN the response MUST be `200` with `items: []`, not `404`
