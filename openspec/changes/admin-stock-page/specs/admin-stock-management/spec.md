# Delta for Admin Stock Management

## ADDED Requirements

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

## MODIFIED Requirements

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
