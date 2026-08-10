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
aggregate with database-generated ids. Registration MUST succeed with zero
initial stock — an initial stock movement MUST NOT be required.

#### Scenario: Create with variants and no stock

- GIVEN a new product with a caller-supplied unique `slug` and one or more
  variants, and no initial stock movement requested
- WHEN the product is registered
- THEN the product and all variants MUST persist and MUST be retrievable,
  with zero recorded stock movements

#### Scenario: Create returns generated ids

- GIVEN a successful product registration
- WHEN the returned aggregate is inspected
- THEN the product and every variant MUST carry a non-null `id` assigned by
  the database

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

Registering a product whose `slug` already exists MUST be rejected,
matching the database's unique constraint on `slug`.

#### Scenario: Duplicate slug rejected

- GIVEN a product already persisted with `slug = "iphone-15"`
- WHEN a new product registration is attempted with the same `slug`
- THEN the registration MUST be rejected and no new product row MUST be
  created

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
