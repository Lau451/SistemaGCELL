# Delta for Admin Stock Management

## ADDED Requirements

### Requirement: Admin Views Per-Variant Movement History

The admin product detail page MUST expose, per variant, a read-only view
of that variant's recorded stock movements (newest first), backed by the
movement history endpoint, with a "Load more" control that appends older
pages using the previous page's `next_before_id` as the cursor. The view
MUST NOT display a computed running/resulting balance per row, and MUST
NOT expose any filter by movement type or date range.

#### Scenario: Admin views a variant's history

- GIVEN an admin is viewing a product with variants that have recorded
  movements
- WHEN the admin selects a variant's history view
- THEN the most recent 20 movements for that variant MUST render
  newest-first

#### Scenario: Load more appends older movements without resetting the list

- GIVEN a variant's history view is showing its first page
- WHEN the admin clicks "Load more"
- THEN the next page of strictly older movements MUST be appended below
  the current list

#### Scenario: A variant with no movements renders an empty state

- GIVEN a variant with zero recorded `stock_movements` rows
- WHEN the admin opens that variant's history view
- THEN the view MUST render an empty state, not an error

#### Scenario: Recording a movement resets the history view to page one

- GIVEN an admin has loaded a second page of a variant's history
- WHEN the admin records a new movement for that variant and the page
  refreshes
- THEN the history view MUST reset to showing only the first page, with
  cursor state cleared

### Requirement: Movement History Ownership Is Checked Before Any Read

A `variant_id` that does not exist, or that belongs to a product other
than the `product_id` in the URL path, MUST be rejected as not-found
before any `stock_movements` history query is attempted. The response
MUST be `404`, never a `403` that confirms the variant exists, mirroring
the existing ownership-check behavior already required for the
record-movement write route.

#### Scenario: History for a variant of another product is rejected

- GIVEN product `A` and product `B` each have at least one variant
- WHEN an admin requests movement history scoped to product `A`
  referencing a `variant_id` that belongs to product `B`
- THEN the response MUST be `404`

#### Scenario: History for an unknown variant id is rejected

- GIVEN a `variant_id` that does not exist in the system
- WHEN an admin requests movement history referencing it
- THEN the response MUST be `404`

## MODIFIED Requirements

### Requirement: Stock Endpoints Require Admin Authorization

The current-stock read route, the record-movement write route, and the
movement-history read route MUST all run only after `verify_admin_jwt`
passes on the `/admin` router, with no separate or weaker check.
(Previously: only covered the current-stock read and record-movement
write routes.)

#### Scenario: Movement write without a JWT is rejected

- GIVEN a `POST .../stock/movements` request with no `Authorization`
  header
- WHEN the request reaches the `/admin` router
- THEN it MUST be rejected with `401 Unauthorized`
- AND no `stock_movements` insert MUST occur

#### Scenario: Current-stock read without a JWT is rejected

- GIVEN a `GET .../stock` request with no `Authorization` header
- WHEN the request reaches the `/admin` router
- THEN it MUST be rejected with `401 Unauthorized`

#### Scenario: Movement history read without a JWT is rejected

- GIVEN a `GET .../stock/movements` request with no `Authorization`
  header
- WHEN the request reaches the `/admin` router
- THEN it MUST be rejected with `401 Unauthorized`
- AND no `stock_movements` query MUST occur
