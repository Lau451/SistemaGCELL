# Delta for Admin Product Management

## ADDED Requirements

### Requirement: Product Detail Page Renders A Variant Switcher For Multi-Variant Products

The admin product detail page MUST render a server-rendered link row
letting the admin choose which variant's stock movement history is
displayed, when the product has two or more variants. The switcher MUST
render nothing (no control, no wrapper markup) when the product has fewer
than two variants. Selecting a link MUST update only which variant's
history is shown; it MUST NOT affect any other section of the page.

#### Scenario: A multi-variant product shows one link per variant

- GIVEN a product with three variants
- WHEN the admin opens that product's detail page
- THEN the page MUST render a link row with exactly one link per variant

#### Scenario: A single-variant product renders no switcher

- GIVEN a product with exactly one variant
- WHEN the admin opens that product's detail page
- THEN the page MUST NOT render any variant switcher control

#### Scenario: Selecting a variant link updates the displayed movement history

- GIVEN a product with two variants, both with recorded movements
- WHEN the admin selects the second variant's link in the switcher
- THEN the page MUST display the second variant's movement history
- AND it MUST NOT display the first variant's movement history

### Requirement: Variant Selection Is URL-Driven And Backward Compatible

The active variant MUST be determined by a `?variant=<id>` query parameter
on the product detail page URL. When `?variant=` is absent, the page MUST
default to the product's first variant, so every existing bookmarked or
shared URL that predates the switcher continues to work unchanged.

#### Scenario: A URL without ?variant defaults to the first variant

- GIVEN a product with two variants
- WHEN the admin opens the product detail page with no `?variant=` query
  parameter
- THEN the page MUST display the first variant's movement history, exactly
  as it did before the switcher existed

#### Scenario: A URL with a valid ?variant shows that variant's history

- GIVEN a product with two variants
- WHEN the admin opens the product detail page with `?variant=` set to the
  second variant's id
- THEN the page MUST display the second variant's movement history

### Requirement: Switching Variants Preserves The Active Date Filter

Each variant switcher link MUST carry forward any active `since`/`until`
date filter alongside the `variant` parameter, so switching variants never
silently clears a filter the admin already applied.

#### Scenario: A switcher link preserves an active date filter

- GIVEN the admin has an active `since`/`until` filter applied on one
  variant's history view
- WHEN the admin inspects the switcher's link for another variant
- THEN that link's URL MUST include the same `since` and `until` values as
  the currently active filter

### Requirement: An Unknown, Foreign, Or Malformed ?variant Returns 404

A `?variant=` value that does not match any variant belonging to the
product being viewed MUST resolve to `404`, never a silent fallback to the
first variant and never `403`. This includes a variant id belonging to a
different product, a nonexistent variant id, and a malformed value. The
membership check MUST run before any movement history is fetched.

#### Scenario: A nonexistent variant id 404s

- GIVEN a product with two variants
- WHEN the admin opens the product detail page with `?variant=` set to an
  id that does not belong to any variant
- THEN the response MUST be `404`
- AND no movement history request MUST be issued

#### Scenario: A variant id belonging to another product 404s, never falls back

- GIVEN product `A` and product `B` each have at least one variant
- WHEN the admin opens product `A`'s detail page with `?variant=` set to a
  variant id belonging to product `B`
- THEN the response MUST be `404`
- AND the page MUST NOT render product `A`'s first variant's history
  instead

#### Scenario: A malformed variant value 404s

- GIVEN a product with two variants
- WHEN the admin opens the product detail page with `?variant=` set to a
  value that is not a valid variant id
- THEN the response MUST be `404`

### Requirement: The Record-Movement Variant Selector Stays Independent Of The URL-Driven Switcher

`StockManager`'s variant selector, used to choose which variant a new
stock movement is recorded against, MUST remain entirely independent of
the `?variant=` query parameter. Switching the active variant via the
switcher MUST NOT pre-select, filter, or otherwise change that selector's
options or current selection.

#### Scenario: Switching the displayed variant does not affect the record-movement selector

- GIVEN the admin has an in-progress movement quantity and reason entered
  in the record-movement form for one variant
- WHEN the admin switches the displayed history to a different variant via
  the switcher
- THEN the record-movement selector's current selection and in-progress
  input MUST remain unchanged
