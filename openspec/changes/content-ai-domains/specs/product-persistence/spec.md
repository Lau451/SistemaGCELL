# Delta for Product Persistence

## MODIFIED Requirements

### Requirement: Product And Variant Aggregate Identity

The `Product` entity MUST expose `id` (UUID), `slug`, `name`, `model`,
`description` (`str | None`), and `short_description` (`str | None`); the
`ProductVariant` entity MUST expose `id` (UUID), `color`, `price`
(`Decimal`), `cost` (`Decimal`), and a reference to its parent product's
`id`. Both entities MUST implement equality and hashing based on `id`, not
on field values.
(Previously: `Product` exposed only `id`, `slug`, `name`, and `model` —
`description` and `short_description` are new optional fields, both
defaulting to `None`.)

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

#### Scenario: Description fields default to None

- GIVEN a `Product` constructed without `description` or
  `short_description`
- WHEN those fields are inspected
- THEN both MUST be `None`, and construction MUST NOT fail

## ADDED Requirements

### Requirement: Repository Round-Trips Product Description Fields

The repository port's create, update, and read operations MUST persist
and return `description` and `short_description` unchanged. The Postgres
adapter and the in-memory adapter MUST implement this identically in
observable behavior, and adapter-parity tests MUST cover both fields.

#### Scenario: Description fields round-trip through create and read

- GIVEN a new product registered with a `description` and a
  `short_description`
- WHEN it is read back via `get_by_id` or `get_by_slug`
- THEN both fields MUST match exactly what was submitted

#### Scenario: Update persists a change to either field independently

- GIVEN an existing product with both fields set
- WHEN `update` changes only `short_description`
- THEN the new `short_description` MUST persist
- AND `description` MUST remain unchanged

#### Scenario: In-memory and Postgres adapters agree on both fields

- GIVEN the same sequence of create/update/read operations exercising
  `description` and `short_description`
- WHEN run against the in-memory adapter and the Postgres adapter
  separately
- THEN both adapters MUST return the same values for both fields
