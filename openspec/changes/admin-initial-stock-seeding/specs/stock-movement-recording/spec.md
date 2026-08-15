# Delta for Stock Movement Recording

## ADDED Requirements

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
