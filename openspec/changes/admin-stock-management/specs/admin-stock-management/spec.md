# Admin Stock Management Specification

## Purpose

Admin-facing read and write path over the existing `stock/` domain: record a
movement, view current per-variant stock, embedded in the product edit page.
Zero changes to `stock/` domain, application, or infrastructure layers — this
spec covers only the admin route contract and admin UI behavior exposing the
already-specified `stock-movement-recording` use cases.

## Requirements

### Requirement: Stock Endpoints Require Admin Authorization

Both the current-stock read route and the record-movement write route MUST
run only after `verify_admin_jwt` passes on the `/admin` router, with no
separate or weaker check.

#### Scenario: Movement write without a JWT is rejected
- GIVEN a `POST .../stock/movements` request with no `Authorization` header
- WHEN the request reaches the `/admin` router
- THEN it MUST be rejected with `401 Unauthorized`
- AND no `stock_movements` insert MUST occur

#### Scenario: Current-stock read without a JWT is rejected
- GIVEN a `GET .../stock` request with no `Authorization` header
- WHEN the request reaches the `/admin` router
- THEN it MUST be rejected with `401 Unauthorized`

### Requirement: Movement Ownership Is Checked Before Any Write

A `variant_id` that does not exist, or that belongs to a product other than
the `product_id` in the URL path, MUST be rejected as not-found before any
`stock_movements` insert is attempted. The response MUST be `404`, never a
`403` that confirms the variant exists, and never a successful mutation.

#### Scenario: Movement for a variant of another product is rejected
- GIVEN product `A` and product `B` each have at least one variant
- WHEN an admin records a movement scoped to product `A` referencing a
  `variant_id` that belongs to product `B`
- THEN the response MUST be `404`
- AND no `stock_movements` row MUST be inserted

#### Scenario: Movement for an unknown variant id is rejected
- GIVEN a `variant_id` that does not exist in the system
- WHEN an admin records a movement referencing it
- THEN the response MUST be `404`
- AND no `stock_movements` row MUST be inserted

### Requirement: Movement Request Validation Runs Before Persistence

An invalid movement request (unknown `movement_type`, or a `quantity_delta`
whose sign does not match its type) MUST be rejected by the route with `422
Unprocessable Entity` and MUST leave no database write, by surfacing the
domain-level rejection already required by `stock-movement-recording`
without duplicating that validation logic at the route layer.

#### Scenario: Unknown movement type yields 422 with no write
- GIVEN a request body with `movement_type = "theft"`
- WHEN it is submitted to the record-movement route
- THEN the response MUST be `422 Unprocessable Entity`
- AND no `stock_movements` row MUST be inserted

#### Scenario: Wrong-sign delta yields 422 with no write
- GIVEN a request body with `movement_type = "sale"` and
  `quantity_delta = 5` (positive)
- WHEN it is submitted to the record-movement route
- THEN the response MUST be `422 Unprocessable Entity`
- AND no `stock_movements` row MUST be inserted

### Requirement: Current-Stock Route Surfaces Per-Variant Quantities

The current-stock GET route MUST return `quantity_on_hand` for every active
variant of the addressed product, sourced from the same current-stock query
already required by `stock-movement-recording`, so the sum of recorded
movements is what the admin view displays.

#### Scenario: Stock view reflects recorded movements
- GIVEN a variant with recorded movements `+10` (restock) and `-3` (sale)
- WHEN an admin requests current stock for that product
- THEN the returned quantity for that variant MUST be `7`

#### Scenario: A newly created variant reads zero stock
- GIVEN a variant created with no `stock_movements` rows yet
- WHEN an admin requests current stock for that product
- THEN the returned quantity for that variant MUST be `0`
- AND it MUST become non-zero only after a movement is recorded

### Requirement: Reason Is Optional On Every Movement Type

The record-movement request body MUST accept `reason` as optional for every
`movement_type`, including `adjustment` and `breakage`; the route MUST NOT
require a reason for any type.

#### Scenario: Adjustment without a reason succeeds
- GIVEN a request body with `movement_type = "adjustment"`,
  `quantity_delta = -2`, and no `reason` field
- WHEN it is submitted to the record-movement route
- THEN the movement MUST be recorded successfully

### Requirement: Admin UI Derives Movement Sign From Type

The record-movement form MUST accept only a positive quantity magnitude from
the admin and MUST derive the submitted `quantity_delta`'s sign from the
selected `movement_type` client-side, so a wrong-sign submission is
unreachable through the UI.

#### Scenario: Admin enters a positive magnitude for a sale
- GIVEN an admin selects `movement_type = "sale"` and enters `3`
- WHEN the form submits
- THEN the request MUST carry `quantity_delta = -3`

### Requirement: Zero-Stock Variants Are Visually Distinguished

The admin stock view MUST render a variant at `0` quantity with styling
distinct from non-zero variants, using a plain zero/non-zero distinction with
no configurable threshold.

#### Scenario: A zero-stock variant renders with distinct styling
- GIVEN a variant whose current stock is `0`
- WHEN the admin stock view renders that product
- THEN that variant's row MUST carry visually distinct styling from
  non-zero variant rows
