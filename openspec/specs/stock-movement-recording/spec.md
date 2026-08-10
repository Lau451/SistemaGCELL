# Stock Movement Recording Specification

## Purpose

Backend application-level behavior for recording append-only stock
movements against existing product variants and deriving current stock,
owned by the `stock/` domain (depending on `products/`, never the
reverse). This spec covers use-case and repository-contract behavior only;
the underlying append-only ledger table, its mutation-rejecting trigger,
and the `variant_stock_levels` derivation are already specified by
`inventory-schema` and are not restated here.

## Requirements

### Requirement: Record Stock Movement Use Case

The application MUST expose a use case that accepts an existing
`variant_id`, a `movement_type`, a non-zero `quantity_delta`, and an
optional `reason`, and persists it as a new `stock_movements` row via the
`StockMovementRepository` port. The port MUST NOT expose any update or
delete operation for movements.

#### Scenario: Recording a valid movement succeeds

- GIVEN an existing variant with no prior movements
- WHEN a movement is recorded with `movement_type = "restock"` and
  `quantity_delta = 10`
- THEN a new movement row MUST be persisted and attributed to that variant

#### Scenario: Repository port has no mutation path

- GIVEN the `StockMovementRepository` port's public interface
- WHEN it is inspected
- THEN it MUST NOT declare an update or delete method for movements,
  matching the append-only invariant

### Requirement: Movement Type And Sign Are Validated In The Domain

The domain MUST validate `movement_type` against the full set of
schema-allowed values (`restock`, `sale`, `return`, `breakage`,
`adjustment`) and MUST validate `quantity_delta` sign per type
(`restock`/`return` positive, `sale`/`breakage` negative, `adjustment`
either sign, always non-zero) before attempting persistence, so an invalid
movement is rejected at the domain layer rather than relying solely on the
database constraint.

#### Scenario: Each allowed movement type is accepted with correct sign

- GIVEN a valid `variant_id`
- WHEN a movement is recorded for each of `restock` (+), `sale` (-),
  `return` (+), `breakage` (-), and `adjustment` (either sign)
- THEN every recording MUST succeed

#### Scenario: Unknown movement type is rejected

- GIVEN a valid `variant_id`
- WHEN a movement is recorded with `movement_type = "theft"`
- THEN the use case MUST reject it before any database write is attempted

#### Scenario: Wrong-sign quantity for type is rejected

- GIVEN a valid `variant_id`
- WHEN a `sale` movement is recorded with `quantity_delta = 5` (positive)
- THEN the use case MUST reject it before any database write is attempted

### Requirement: Current Stock Is Read Via A Separate Query

Current per-variant stock MUST be exposed only through a dedicated read
operation backed by the `variant_stock_levels` view, and MUST NOT be
hydrated as a field on `ProductVariant`, keeping the `stock/` domain's read
model out of the `products/` aggregate.

#### Scenario: Stock query reflects recorded movements

- GIVEN a variant with recorded movements `+10` (restock) and `-3` (sale)
- WHEN the current-stock query is run for that variant
- THEN it MUST return `7`

#### Scenario: ProductVariant does not carry stock

- GIVEN a `ProductVariant` instance returned by the product repository
- WHEN its fields are inspected
- THEN it MUST NOT expose a stock/quantity field
