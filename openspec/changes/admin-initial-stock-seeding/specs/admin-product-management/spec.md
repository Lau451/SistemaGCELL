# Delta for Admin Product Management

## ADDED Requirements

### Requirement: Product Creation Accepts An Optional Initial Quantity Per Variant

`POST /admin/products` MUST accept an optional `initial_quantity` integer
(default `0`, `Field(ge=0)`) on each variant in the request body. When a
variant's `initial_quantity` is greater than `0`, the system MUST record
exactly one `restock` stock movement for that variant, persisted in the
same atomic transaction as the product and its variant rows. When
`initial_quantity` is `0` or absent, the system MUST NOT construct or
record any stock movement for that variant. `PATCH /admin/products/{id}`
MUST accept the same variant input shape (which carries this field) but
MUST NOT read or act on `initial_quantity` — the field is silently
accepted and ignored on that route.

#### Scenario: Creating a product with a positive initial quantity seeds one restock movement

- GIVEN an admin submits `POST /admin/products` with one new variant
  carrying `initial_quantity: 5`
- WHEN the product is created
- THEN the product and variant MUST persist
- AND exactly one `restock` stock movement of quantity `5` MUST be
  recorded for that variant, in the same transaction as the creation

#### Scenario: Creating a product with zero or absent initial quantity records no movement

- GIVEN an admin submits `POST /admin/products` with a new variant whose
  `initial_quantity` is `0` or omitted
- WHEN the product is created
- THEN the product and variant MUST persist
- AND no stock movement MUST be constructed or recorded for that variant

#### Scenario: A negative initial quantity is rejected before any write

- GIVEN an admin submits `POST /admin/products` with a variant carrying
  `initial_quantity: -1`
- WHEN the request is validated
- THEN the API MUST return `422`
- AND no domain object or database write MUST be attempted

#### Scenario: A failure recording a seed movement rolls back the whole creation

- GIVEN an admin submits `POST /admin/products` with two new variants,
  one carrying `initial_quantity: 3`
- WHEN recording that variant's seed movement fails
- THEN neither variant row NOR the product row MUST remain persisted
  afterward

#### Scenario: PATCH accepts but ignores initial_quantity

- GIVEN an existing product with an existing variant
- WHEN the admin submits `PATCH /admin/products/{id}` with a variant
  input that includes `initial_quantity: 5`
- THEN the request MUST succeed with no error
- AND no stock movement MUST be recorded as a result of that field
