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

### Requirement: List Variant Stock Movements Use Case

The application MUST expose a read-only use case that lists a variant's
persisted `stock_movements` rows via a new `StockMovementHistoryReader`
port, ordered `id DESC` (newest first), accepting a `limit` (default 20,
server-side hard cap 100 — values above the cap MUST be clamped, not
rejected) and an optional `before_id` exclusive keyset cursor. This port
MUST be separate from the write-only `StockMovementRepository` — the
existing port's single `record` method MUST NOT grow a read method, and
the no-update/no-delete invariant on `StockMovementRepository` remains
unchanged by this requirement.

#### Scenario: History reflects recorded movements newest-first

- GIVEN a variant with movements recorded in order `+10` (restock), `-3`
  (sale), `+2` (return)
- WHEN the history use case lists that variant's movements
- THEN the returned rows MUST be ordered newest-first by `id DESC`

#### Scenario: Cursor pagination returns strictly older rows with no gaps or duplicates

- GIVEN a variant with more than `limit` movements
- WHEN a first page is fetched, then a second page is fetched using the
  first page's `next_before_id` as `before_id`
- THEN every row on the second page MUST have an `id` strictly less than
  every row on the first page
- AND no row MUST appear on both pages

#### Scenario: Limit above the hard cap is clamped, not rejected

- GIVEN a request for movement history with `limit = 500`
- WHEN the use case executes
- THEN it MUST clamp the effective limit to `100` rather than rejecting
  the request

#### Scenario: StockMovementRepository gains no new method

- GIVEN the `StockMovementRepository` port's public interface
- WHEN it is inspected after this change
- THEN it MUST still declare only the `record` method, with history reads
  served exclusively by the separate `StockMovementHistoryReader` port

### Requirement: Atomic Registration Of A New Product With Initial Stock Movements

The application MUST expose an atomic composition — reusing the existing
`RegisterStockedProductUseCase` — that persists a new product, its
variants, and zero or more initial `restock` stock movements in one
transaction, reachable from the admin product creation route. A movement
MUST be constructed only for a variant whose seed quantity is greater
than `0`; the domain's existing non-zero `quantity_delta` invariant on
`StockMovement` MUST be relied upon, never bypassed, so a zero-delta
movement is never constructed or persisted. Any failure at any step of
the composition (product insert, variant insert, or movement recording)
MUST roll back every part of it — nothing is left partially persisted.

#### Scenario: Registering a product with a positive seed quantity records one movement per such variant

- GIVEN a new product with two variants, one with seed quantity `4` and
  one with seed quantity `0`
- WHEN the atomic registration composition runs
- THEN the product and both variants MUST persist
- AND exactly one `restock` movement MUST be recorded, for the variant
  with seed quantity `4`

#### Scenario: A zero or absent seed quantity never produces a movement

- GIVEN a new product where every variant has seed quantity `0` or
  unspecified
- WHEN the atomic registration composition runs
- THEN the product and its variants MUST persist
- AND zero stock movements MUST be recorded

#### Scenario: A mid-composition failure rolls back product, variants, and movements together

- GIVEN a new product with one variant carrying a positive seed quantity
- WHEN the movement-recording step of the composition fails
- THEN the product row and the variant row MUST NOT remain persisted
- AND no partial movement row MUST exist

#### Scenario: The composition never bypasses the non-zero movement invariant

- GIVEN a caller of the composition attempts to pass a seed quantity of
  `0` for a variant
- WHEN the composition builds the set of movements to record
- THEN it MUST NOT construct a `StockMovement` for that variant at all,
  relying on `StockMovement`'s existing rejection of a zero
  `quantity_delta` as a backstop, not as the primary mechanism
