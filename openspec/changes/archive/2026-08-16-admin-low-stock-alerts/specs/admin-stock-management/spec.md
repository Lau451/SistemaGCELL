# Delta for Admin Stock Management

## ADDED Requirements

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
