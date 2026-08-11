# Product Persistence Specification

## Purpose

Backend domain model, repository port, and Postgres adapter for persisting
products and their variants for admin writes, keyed by `slug` — the only
DB-unique business identifier — not `name`.

## Requirements

### Requirement: Product And Variant Aggregate Identity

The `Product` entity MUST expose `id` (UUID), `slug`, `name`, and `model`;
the `ProductVariant` entity MUST expose `id` (UUID), `color`, `price`
(`Decimal`), `cost` (`Decimal`), and a reference to its parent product's
`id`. Both entities MUST implement equality and hashing based on `id`, not
on field values.

#### Scenario: Equality is id-based

- GIVEN two `Product` instances constructed with the same `id` but
  different `name` values
- WHEN they are compared for equality
- THEN they MUST compare equal

#### Scenario: Distinct ids are never equal

- GIVEN two `Product` instances with different `id` values and otherwise
  identical fields
- WHEN they are compared for equality
- THEN they MUST compare not equal

#### Scenario: Money fields are Decimal

- GIVEN a `ProductVariant` constructed with `price` and `cost` values
- WHEN those fields are inspected
- THEN both MUST be `Decimal` instances, never `float`

### Requirement: Repository Create Persists Product With Variants

The repository port MUST expose an operation that persists a new product
together with one or more variants in a single call, returning the hydrated
aggregate with database-generated ids. `slug` MUST be derived server-side
from `name` (kebab-case) and MUST NOT be accepted as a caller-supplied
value; a collision with an existing slug MUST be resolved by appending a
numeric suffix before insert. Registration MUST succeed with zero initial
stock — an initial stock movement MUST NOT be required.

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

### Requirement: Repository Reads By Slug And By Id

The repository port MUST expose `get_by_slug` and `get_by_id` operations.
`get_by_name` MUST NOT be used for lookups or duplicate checks, since
`slug` — not `name` — is the DB-unique key.

#### Scenario: Get by slug returns persisted product

- GIVEN a previously persisted product with a known `slug`
- WHEN `get_by_slug` is called with that `slug`
- THEN the matching product with its variants MUST be returned

#### Scenario: Get by id returns persisted product

- GIVEN a previously persisted product with a known `id`
- WHEN `get_by_id` is called with that `id`
- THEN the matching product with its variants MUST be returned

#### Scenario: Unknown slug yields not-found

- GIVEN no product exists with a given `slug`
- WHEN `get_by_slug` is called with that `slug`
- THEN the repository MUST report not-found rather than raising an
  unrelated error

### Requirement: Duplicate Slug Is Rejected On Registration

Because `slug` is server-derived with numeric-suffix collision resolution,
callers MUST NOT be able to trigger a duplicate-slug rejection through
normal use — the generator MUST re-check existing slugs and pick the next
available suffix before insert. The database's unique constraint on `slug`
MUST remain as a final safety net: if a duplicate slug is nonetheless
proposed for insert (e.g. a race between two concurrent registrations), the
second insert MUST be rejected and MUST leave no partial row.

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

### Requirement: Product-With-Variants Insert Is Atomic

Inserting a product together with its variants (and an optional initial
stock movement) MUST run inside a single database transaction. Any failure
partway through MUST leave no partial rows — neither the product, any
variant, nor any movement.

#### Scenario: Failure leaves no partial rows

- GIVEN a product registration with two variants where the second
  variant's data violates a database constraint
- WHEN the registration is attempted
- THEN the operation MUST fail AND neither the product row nor the first
  variant row MUST remain persisted

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
