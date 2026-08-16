# Delta for Admin Stock Management

## ADDED Requirements

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

## MODIFIED Requirements

### Requirement: Zero-Stock Variants Are Visually Distinguished

Both the per-product admin stock view and the admin product list (which
now renders per-variant stock) MUST render a variant at `0` quantity with
styling distinct from non-zero variants, using the same plain zero/non-zero
distinction with no configurable threshold, kept consistent across both
surfaces.
(Previously: applied only to the per-product admin stock view.)

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
