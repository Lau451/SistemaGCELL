# Inventory Schema Specification

## Purpose

Defines the append-only stock movements ledger. Current stock is always
derived from the ledger, never stored as a mutable counter, so movement
history (restock, sale, return, breakage) is never lost.

## Requirements

### Requirement: Stock Movements Are Append-Only

`stock_movements` MUST accept row inserts recording `variant_id`,
`movement_type`, `quantity_delta`, `reason`, and `created_at`, and MUST NOT
expose any path (grant, policy, or trigger) that allows an existing row's
`quantity_delta` to be updated after insert.

#### Scenario: Movement insert succeeds

- GIVEN an existing variant
- WHEN a `service_role` client inserts a stock movement row for that variant
- THEN the insert MUST succeed and the row MUST be immutable afterward

#### Scenario: No UPDATE path exists on movement quantity

- GIVEN an existing `stock_movements` row
- WHEN any role attempts `UPDATE stock_movements SET quantity_delta = ...`
- THEN the operation MUST fail (no UPDATE grant/policy permits it) for every
  role, including `service_role`

### Requirement: Current Stock Is Derived, Not Stored

Per-variant current stock MUST be computed as `SUM(quantity_delta)` over that
variant's `stock_movements` rows, not read from a stored counter column.

#### Scenario: Stock reflects sum of movements

- GIVEN a variant with movements `+10`, `-3`, `+2`
- WHEN current stock is queried
- THEN the result MUST equal `9`

### Requirement: Public Visibility Is a Boolean Only

`anon` MUST see only a derived `in_stock` boolean per variant through the
public catalog view; `anon` MUST NOT be able to read `quantity_delta`, exact
stock counts, or any row of `stock_movements`.

#### Scenario: anon sees in_stock, not a count

- GIVEN a variant with derived stock `9`
- WHEN `anon` reads the public catalog view
- THEN the row MUST expose `in_stock = true` and MUST NOT expose a numeric
  quantity field

#### Scenario: anon denied on stock_movements base table

- GIVEN the `anon` role
- WHEN it attempts to select from `stock_movements`
- THEN the query MUST return zero rows or an authorization error

### Requirement: Service Role Reads Full Movement History

`service_role` MUST be able to read every `stock_movements` row, including
`quantity_delta` and `reason`, for audit purposes.

#### Scenario: service_role queries movement history

- GIVEN multiple movements exist for a variant
- WHEN `service_role` selects all `stock_movements` rows for that variant
- THEN every row MUST be returned with its original `quantity_delta` and
  `reason` intact
