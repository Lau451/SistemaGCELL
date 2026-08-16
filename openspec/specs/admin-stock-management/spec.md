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

#### Scenario: Movement history read without a JWT is rejected
- GIVEN a `GET .../stock/movements` request with no `Authorization` header
- WHEN the request reaches the `/admin` router
- THEN it MUST be rejected with `401 Unauthorized`
- AND no `stock_movements` query MUST occur

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

### Requirement: Bulk Catalog-Wide Current-Stock Read

The stock capability MUST expose a bulk current-stock read returning
`dict[UUID, int]` (variant_id → current quantity) for every variant in the
catalog via exactly one aggregate query, independent of and without
replacing the existing per-product current-stock read. A variant with no
recorded movements MUST resolve to `0` in the returned dict, never a
missing key or `null`. Both `PostgresStockLevelReader` and
`InMemoryStockLevelReader` MUST implement this method with the same
contract.

#### Scenario: Bulk read returns a quantity for every variant across the whole catalog in one query

- GIVEN a catalog with variants spread across multiple products
- WHEN the bulk current-stock read is invoked
- THEN the returned dict MUST contain a quantity for every variant in the
  catalog
- AND exactly one query MUST be issued against the stock data, regardless
  of variant count

#### Scenario: A variant with zero movements resolves to zero, not a missing key

- GIVEN a variant with no recorded `stock_movements` rows
- WHEN the bulk current-stock read is invoked
- THEN that variant's id MUST be present as a key in the returned dict
- AND its value MUST be `0`

### Requirement: Catalog-Wide Stock Triage Ordering, Threshold, And Search

The catalog-wide stock triage view MUST list every variant sorted ascending
by current quantity by default, with no implicit or hardcoded threshold
applied when no filter is given. An optional threshold filter MUST narrow
the list to variants whose quantity is less than or equal to the given value
(inclusive), including `0` as a meaningful threshold that returns only
out-of-stock variants (never an empty result and never silently
reinterpreted as "no filter"); a negative threshold clamps to `0` rather
than erroring. An optional text search MUST match a variant's row when the query
is a case-insensitive substring of either the product's name or the
variant's color — matching either field satisfies the search, a single
search box, not two separate fields. When both a threshold and a search
query are supplied together, a row MUST satisfy both conditions (logical
AND); it MUST NOT be included by satisfying only one.

#### Scenario: Default view is ascending by quantity with no implicit filtering

- GIVEN a catalog with variants at varying quantities, including some above
  any conventional low-stock level
- WHEN the triage view is requested with no threshold and no search
- THEN every variant in the catalog MUST be present in the result
- AND results MUST be ordered by quantity ascending

#### Scenario: A threshold narrows to variants below it

- GIVEN variants with quantities 0, 3, and 10
- WHEN the triage view is requested with a threshold of 5
- THEN only the variants with quantities 0 and 3 MUST be included

#### Scenario: A threshold of zero returns only out-of-stock variants

- GIVEN variants with quantities 0, 3, and 10
- WHEN the triage view is requested with a threshold of 0
- THEN only the variant with quantity 0 MUST be included
- AND the result MUST NOT be empty or equivalent to "no filter applied"

#### Scenario: Search matches product name case-insensitively

- GIVEN a product named "Funda Silicona" with a variant colored "Rojo"
- WHEN the triage view is searched for "funda"
- THEN that variant's row MUST be included

#### Scenario: Search matches variant color case-insensitively

- GIVEN a product named "Cargador" with a variant colored "Negro"
- WHEN the triage view is searched for "negro"
- THEN that variant's row MUST be included

#### Scenario: Search and threshold combine with AND

- GIVEN a variant matching the search text but with a quantity above the
  given threshold
- WHEN the triage view is requested with both that search text and that
  threshold
- THEN that variant's row MUST NOT be included

### Requirement: Zero-Stock Variants Are Visually Distinguished

The per-product admin stock view, the admin product list, and the
catalog-wide stock triage view (which now also renders per-variant stock)
MUST render a variant at `0` quantity with styling distinct from non-zero
variants, using the same plain zero/non-zero distinction with no
configurable threshold, kept consistent across all three surfaces.
(Previously: applied only to the per-product admin stock view and the
admin product list.)

#### Scenario: A zero-stock variant renders with distinct styling on the detail view
- GIVEN a variant whose current stock is `0`
- WHEN the admin stock view renders that product
- THEN that variant's row MUST carry visually distinct styling from
  non-zero variant rows

#### Scenario: A zero-stock variant renders with distinct styling on the admin product list
- GIVEN a variant whose current stock is `0`
- WHEN the admin product list renders that variant's row
- THEN that row MUST carry the same visually distinct zero-stock styling
  used on the per-product detail view

#### Scenario: A zero-stock variant renders with distinct styling on the catalog-wide triage view

- GIVEN a variant whose current stock is `0`
- WHEN the catalog-wide stock triage view renders that variant's row
- THEN that row MUST carry the same visually distinct zero-stock styling
  used on the other two surfaces

#### Scenario: A variant with zero movements reports zero on the triage view

- GIVEN a variant with no recorded `stock_movements` rows
- WHEN the catalog-wide stock triage view renders that variant's row
- THEN its quantity MUST render as `0`, sourced from the same bulk
  current-stock read that resolves zero-movement variants to `0`

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

### Requirement: Admin Nav Low-Stock Badge Count

The admin shell MUST compute a low-stock count on every `/admin/*` page
load and attach it to the "Stock" nav link. The count MUST equal the
number of catalog variants with `quantity <= 5` (a fixed, inclusive
threshold, not admin-configurable), computed by calling the existing
`GET /admin/stock?below=5` route unchanged — the same
`ListCatalogStockLevelsUseCase` and `CatalogStockLevelsReader
.quantities_for_variants()` bulk read already required elsewhere in this
capability. No new query path, no per-variant query, and no new backend
route or port MAY be introduced for this count. This fixed `below=5`
badge default is independent of, and MUST NOT alter, the triage view's
own default (no implicit threshold when the view is requested with no
filter) — the two are separate call sites of the same read path with
different callers supplying different (or no) threshold values.

#### Scenario: Badge count reflects the fixed inclusive threshold

- GIVEN a catalog with variants at quantities 0, 3, 5, 6, and 10
- WHEN the admin shell computes the low-stock count
- THEN the count MUST be `3`, including the variant at exactly `5`

#### Scenario: Count reuses the existing bulk read with no new query path

- GIVEN any `/admin/*` page is requested
- WHEN the admin shell computes the low-stock count
- THEN it MUST call `GET /admin/stock?below=5` unchanged
- AND it MUST NOT issue any additional per-variant query beyond that
  route's existing single aggregate read

#### Scenario: Count reflects the whole catalog, not a partial or paginated subset

- GIVEN a catalog larger than any page size used by the `/admin/stock`
  triage UI
- WHEN the low-stock count is computed
- THEN it MUST include every matching variant across the entire catalog,
  not only variants visible on a first page or any other partial subset

### Requirement: Admin Nav Low-Stock Badge Presentation

The low-stock badge MUST render only as an addition to the existing
"Stock" nav link — it MUST NOT introduce a second triage surface or any
inline stock-editing affordance. At a count of `0` the badge MUST NOT
render at all (no `Stock (0)` state); the link MUST appear exactly as it
does today. At any non-zero count, the badge MUST render the exact count
using the existing `text-destructive` styling convention already applied
to zero-stock rows elsewhere in the admin, and activating it (click or
equivalent) MUST navigate to `/admin/stock`.

#### Scenario: A zero low-stock count hides the badge entirely

- GIVEN a catalog with zero variants at `quantity <= 5`
- WHEN the admin shell renders the "Stock" nav link
- THEN no badge or count text MUST render beside it
- AND the link MUST NOT render as `Stock (0)`

#### Scenario: A non-zero count renders with the existing destructive styling

- GIVEN the computed low-stock count is `3`
- WHEN the "Stock" nav link renders
- THEN it MUST display `Stock (3)`
- AND the count MUST use the same `text-destructive` styling convention
  used for zero-stock rows elsewhere in the admin

#### Scenario: Activating the badge navigates to the triage page

- GIVEN the "Stock" nav link is rendered with a non-zero badge
- WHEN an admin clicks it
- THEN the browser MUST navigate to `/admin/stock`
- AND no separate triage or editing surface MUST open in its place
