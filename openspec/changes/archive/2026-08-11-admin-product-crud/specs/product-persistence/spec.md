# Delta for Product Persistence

## MODIFIED Requirements

### Requirement: Repository Create Persists Product With Variants

The repository port MUST expose an operation that persists a new product
together with one or more variants in a single call, returning the hydrated
aggregate with database-generated ids. `slug` MUST be derived server-side
from `name` (kebab-case) and MUST NOT be accepted as a caller-supplied
value; a collision with an existing slug MUST be resolved by appending a
numeric suffix before insert. Registration MUST succeed with zero initial
stock — an initial stock movement MUST NOT be required.
(Previously: slug was caller-supplied and asserted unique by the caller)

#### Scenario: Create with variants and no stock

- GIVEN a new product with `name`, `model`, and one or more variants, and no
  initial stock movement requested
- WHEN the product is registered
- THEN a `slug` MUST be derived from `name` in kebab-case
- AND the product and all variants MUST persist and MUST be retrievable,
  with zero recorded stock movements

#### Scenario: Create returns generated ids

- GIVEN a successful product registration
- WHEN the returned aggregate is inspected
- THEN the product and every variant MUST carry a non-null `id` assigned by
  the database
- AND the product MUST carry its server-derived `slug`

### Requirement: Duplicate Slug Is Rejected On Registration

Because `slug` is server-derived with numeric-suffix collision resolution,
callers MUST NOT be able to trigger a duplicate-slug rejection through
normal use — the generator MUST re-check existing slugs and pick the next
available suffix before insert. The database's unique constraint on `slug`
MUST remain as a final safety net: if a duplicate slug is nonetheless
proposed for insert (e.g. a race between two concurrent registrations), the
second insert MUST be rejected and MUST leave no partial row.
(Previously: registering with an already-existing caller-supplied slug was
rejected outright, with no generator-side collision resolution)

#### Scenario: Same name yields distinct slugs, not a rejection

- GIVEN a product already persisted with slug `iphone-15`, derived from
  name "iPhone 15"
- WHEN a second product is registered with name "iPhone 15"
- THEN the generator MUST derive a distinct slug (e.g. `iphone-15-2`)
- AND both products MUST persist successfully with distinct slugs

#### Scenario: A true duplicate slug is still rejected at the database

- GIVEN a race condition causes two concurrent registrations to compute the
  identical slug
- WHEN both attempt to insert
- THEN the database unique constraint MUST reject the second insert
- AND no partial row MUST remain from the rejected insert

## ADDED Requirements

### Requirement: Slug Is Immutable After Creation

The `slug` value assigned at creation time MUST NOT change for the lifetime
of the product, even when `name` is later changed via the update operation.

#### Scenario: Renaming a product does not change its slug

- GIVEN a persisted product with slug `iphone-15` and name "iPhone 15"
- WHEN the product's `name` is updated to "iPhone 15 Pro" via `update`
- THEN the persisted `slug` MUST remain `iphone-15`

### Requirement: Repository Update Persists Field And Variant Changes Atomically

The repository port MUST expose an `update` operation that persists changes
to a product's mutable fields (`name`, `model`) and applies variant
additions/removals in the same call. `update` MUST NOT accept or alter
`slug`. All changes within one `update` call MUST commit atomically.

#### Scenario: Field and variant changes commit together

- GIVEN an existing product with two variants
- WHEN `update` is called changing `name` and removing one variant while
  adding a new one
- THEN all changes MUST persist together and MUST be visible on the next
  read

#### Scenario: A failed update leaves no partial change

- GIVEN an `update` call where a new variant violates a database constraint
- WHEN `update` is attempted
- THEN neither the field changes nor any variant change from that call MUST
  persist

### Requirement: Repository Soft-Delete Retires A Product Or Variant Without Row Deletion

The repository port MUST expose a `soft_delete` operation covering both a
product and an individual variant. `soft_delete` MUST mark ONLY its own
target row via a single `UPDATE` (never a `DELETE`) and MUST leave
`stock_movements` completely untouched. `soft_delete` MUST NOT require a
product to retain at least one active variant.

Cascade to variants when a product is retired is achieved at READ time, not
by a second write: every read (`get_by_id`, `get_by_slug`, `list_all`, and
the public catalog views) MUST exclude a variant whose parent product is
retired, even though the variant row's own `deleted_at` stays unset. This is
a deliberate design choice (see design.md "product retirement cascades at
read time, not by stamping variants") — it keeps a future restore able to
distinguish "hidden because its parent retired" from "retired individually,"
and keeps retirement a single-row, transaction-free operation.

#### Scenario: Soft-deleting a product hides its variants without writing to them

- GIVEN a product with two active variants and recorded stock movements on
  one variant
- WHEN `soft_delete` is called for the product
- THEN ONLY the product row MUST be marked retired via `UPDATE`
- AND neither variant row's `deleted_at` MUST change
- AND every subsequent read MUST exclude both variants because their parent
  product is retired
- AND every `stock_movements` row referencing those variants MUST remain
  unchanged

#### Scenario: Soft-deleting a single variant does not affect the product or siblings

- GIVEN a product with two active variants
- WHEN `soft_delete` is called for one variant only
- THEN only that variant MUST be marked retired
- AND the product and the other variant MUST remain active
