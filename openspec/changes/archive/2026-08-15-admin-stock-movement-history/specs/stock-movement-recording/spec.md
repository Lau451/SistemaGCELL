# Delta for Stock Movement Recording

## ADDED Requirements

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
