# Delta for Admin Stock Management

## MODIFIED Requirements

### Requirement: Admin Views Per-Variant Movement History

The admin product detail page MUST expose, per variant, a read-only view
of that variant's recorded stock movements (newest first), backed by the
movement history endpoint, with a "Load more" control that appends older
pages using the previous page's `next_before_id` as the cursor. The view
MUST NOT display a computed running/resulting balance per row. The view
MUST NOT expose any filter by movement type. The view MUST expose an
optional date-range filter (`since`/`until`), submitted via the same
endpoint's new optional query parameters, plus three quick presets: today,
last 7 days, and last 30 days, computed client-side. `until` is inclusive
of the entire selected day. An inverted range (`since` later than `until`)
MUST be rejected before any request is sent. The active filter MUST persist
when the admin switches to another variant on the same product page.
Changing the filter MUST reset the view to page one with cursor state
cleared, never mixing pages fetched under different filters.
(Previously: MUST NOT expose any filter by movement type or date range —
the date-range half is reversed per D3; the movement-type half and the
no-balance clause are unchanged.)

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

#### Scenario: A variant with no movements at all renders the no-history empty state

- GIVEN a variant with zero recorded `stock_movements` rows, and no
  date filter applied
- WHEN the admin opens that variant's history view
- THEN the view MUST render an empty state indicating this variant has
  no history at all, not an error

#### Scenario: A date range with no matching movements renders the filtered-empty state

- GIVEN a variant with recorded `stock_movements` rows outside the
  selected date range
- WHEN the admin applies a `since`/`until` filter that matches zero
  movements
- THEN the view MUST render an empty state with copy distinct from the
  no-history-at-all empty state, indicating no movements in this range

#### Scenario: Recording a movement resets the history view to page one

- GIVEN an admin has loaded a second page of a variant's history
- WHEN the admin records a new movement for that variant and the page
  refreshes
- THEN the history view MUST reset to showing only the first page, with
  cursor state cleared

#### Scenario: Applying a date-range preset filters the visible history

- GIVEN a variant with movements spanning more than 30 days
- WHEN the admin selects the "last 7 days" preset
- THEN only movements within the last 7 days MUST render, newest-first

#### Scenario: An inverted date range is rejected before submission

- GIVEN the admin has entered a `since` date later than the `until` date
- WHEN the admin attempts to apply the filter
- THEN the view MUST prevent submission and surface a validation message,
  matching the endpoint's 422 rejection of an inverted range

#### Scenario: The active date filter persists across a variant switch

- GIVEN the admin has an active `since`/`until` filter on one variant's
  history view
- WHEN the admin switches to another variant on the same product page
- THEN the same date filter MUST remain applied to the newly selected
  variant's history view

#### Scenario: Changing the date filter never mixes stale and fresh pages

- GIVEN a variant's history view has a loaded second page under one
  filter
- WHEN the admin changes the `since`/`until` filter
- THEN the view MUST refetch page one under the new filter and MUST NOT
  append the new results to movements loaded under the previous filter

#### Scenario: Movement-type filtering remains unavailable

- GIVEN an admin is viewing any variant's history view
- WHEN the admin looks for a way to filter by movement type
- THEN no such control MUST be present, and the view MUST NOT expose any
  filter by movement type

#### Scenario: No running or resulting balance is ever displayed

- GIVEN an admin is viewing any variant's history view, filtered or
  unfiltered
- WHEN the movements render
- THEN no row MUST display a computed running or resulting balance
