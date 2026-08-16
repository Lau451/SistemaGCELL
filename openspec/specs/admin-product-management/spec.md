# Admin Product Management Specification

## Purpose

Admin-facing create/edit/soft-delete workflows for products and variants:
forms with validation feedback, server-generated slug on create, atomic
field + variant edits, and soft-delete that hides rows from every admin and
public view without ever deleting a row.

## Requirements

### Requirement: Product Creation Form Validates And Persists With A Server-Generated Slug

The admin product creation form MUST validate required fields client-side
and server-side, MUST surface validation feedback without persisting on
invalid submission, and MUST NEVER accept an admin-typed `slug` — the slug
is always derived server-side from `name`.

#### Scenario: Valid submission creates a product with a generated slug

- GIVEN the admin fills a valid name, model, and at least field data for one
  variant
- WHEN the form is submitted
- THEN the product MUST persist with a slug derived from `name`
- AND the admin MUST see the created product, including its slug

#### Scenario: Invalid submission shows feedback and does not persist

- GIVEN the admin submits the form with a missing required field or an
  invalid variant price
- WHEN submission is attempted
- THEN no product row MUST be created
- AND the admin MUST see field-level validation feedback

#### Scenario: Same name across two creations yields distinct slugs

- GIVEN a product named "iPhone 15" already exists
- WHEN the admin creates a second product also named "iPhone 15"
- THEN the second product MUST persist with a distinct, valid slug
- AND creation MUST NOT fail due to the name collision

### Requirement: Product Edit Persists Field And Variant Changes Atomically

The admin edit form MUST allow changing product fields and adding/removing
variants in one submission, and MUST commit all of it atomically.

#### Scenario: Field and variant changes persist together

- GIVEN an existing product with two variants
- WHEN the admin changes the product's `name`, removes one variant, and adds
  a new variant in a single edit submission
- THEN all three changes MUST persist together
- AND a failure in any part MUST leave none of the changes persisted

#### Scenario: Slug never changes after creation, even on rename

- GIVEN a persisted product with slug `iphone-15`
- WHEN the admin edits the product's `name` to "iPhone 15 Pro"
- THEN the persisted `slug` MUST remain `iphone-15`
- AND the edit form MUST NOT expose a slug field to change

### Requirement: Soft-Deleting A Product Cascades To Hide Its Variants

Soft-deleting a product from the admin UI MUST remove it, and all of its
variants, from the admin product list and the public catalog, without
deleting any row.

#### Scenario: Soft-deleted product disappears from the admin list

- GIVEN an active product visible in the admin product list
- WHEN the admin soft-deletes it
- THEN the product MUST NOT appear in the admin product list afterward

#### Scenario: Soft-deleted product disappears from the public catalog

- GIVEN an active product visible in the public catalog
- WHEN the admin soft-deletes it
- THEN the product and all of its variants MUST NOT appear in any public
  catalog read afterward

#### Scenario: Soft-deleting a product hides all of its variants

- GIVEN a product with two active variants
- WHEN the admin soft-deletes the product
- THEN both variants MUST also become hidden from the admin list and the
  public catalog, without a separate per-variant action

### Requirement: A Variant Can Be Retired Independently Of Its Product

The admin UI MUST allow soft-deleting a single variant without affecting the
parent product or its other variants.

#### Scenario: Retiring one variant leaves the product and siblings active

- GIVEN a product with two active variants
- WHEN the admin soft-deletes only one variant
- THEN that variant MUST disappear from admin and public views
- AND the product and its other variant MUST remain fully visible and active

### Requirement: A Product May Have Zero Active Variants Without Being Retired

Removing or soft-deleting a product's last remaining active variant MUST NOT
retire the product itself and MUST NOT be blocked by a "must keep at least
one active variant" rule.

#### Scenario: Removing the last variant leaves the product editable

- GIVEN a product with exactly one active variant
- WHEN the admin soft-deletes that variant
- THEN the product row MUST remain active and MUST still appear in the
  admin product list, editable, with zero variants
- AND the product MUST become effectively invisible in the public catalog
  (no variants to list) without itself being marked deleted

### Requirement: No Restore Capability In This Change

The admin UI MUST NOT provide any action to restore a soft-deleted product
or variant.

#### Scenario: No restore control exists

- GIVEN a soft-deleted product or variant
- WHEN the admin looks for a way to undo the soft-delete in the UI
- THEN no restore/undo control MUST be present anywhere in the admin panel

### Requirement: No "Show Retired" Filter — Soft-Deleted Rows Are Hidden Entirely

Every admin list view (products, and any variant listing within a product)
MUST hide soft-deleted rows unconditionally. No toggle, filter, or query
parameter MUST reveal soft-deleted rows.

#### Scenario: Soft-deleted rows never reappear via a filter or toggle

- GIVEN one soft-deleted product and one soft-deleted variant on an
  otherwise-active product
- WHEN the admin views any admin list screen, with or without any filter
  control interacted with
- THEN neither the soft-deleted product nor the soft-deleted variant MUST
  ever be rendered

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
