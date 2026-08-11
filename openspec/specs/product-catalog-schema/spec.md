# Product Catalog Schema Specification

## Purpose

Defines the durable Postgres schema for products, variants, and images — the
data contract the public catalog and admin panel build on. Base tables deny
`anon`; public reads happen only through views.

## Requirements

### Requirement: Product Identity and Slug Uniqueness

The `products` table MUST use a UUID surrogate primary key and MUST enforce a
unique, non-blank `slug` column used for public catalog URLs.

#### Scenario: Duplicate slug rejected

- GIVEN a product exists with slug `fundas-iphone-15`
- WHEN a second product is inserted with the same slug
- THEN the insert MUST fail on a uniqueness constraint

#### Scenario: Blank slug or name rejected

- GIVEN a new product row with an empty or null `name`, `model`, or `slug`
- WHEN the insert is attempted
- THEN the insert MUST fail on a check constraint

### Requirement: Product Variants Carry Color and Non-Negative Pricing

`product_variants` MUST reference its parent product via a foreign key, MUST
include a `color` column, and MUST enforce non-negative `price` and `cost`.

#### Scenario: Negative price rejected

- GIVEN a variant insert with `price = -1`
- WHEN the insert is attempted
- THEN the insert MUST fail on a check constraint

#### Scenario: Variant deleted when parent product is deleted

- GIVEN a product with at least one variant
- WHEN the product row is deleted
- THEN the FK delete behaviour MUST resolve deterministically (cascade or
  restrict) with no orphaned variant rows left referencing a missing product

### Requirement: Product Images Reference a Variant

`product_images` MUST reference an existing `product_variants` row via a
foreign key and MUST NOT permit an image row with no valid parent variant.

#### Scenario: Image insert without valid variant rejected

- GIVEN no variant exists with id `X`
- WHEN a `product_images` row is inserted referencing variant `X`
- THEN the insert MUST fail on the foreign key constraint

### Requirement: Public Catalog Reads Exclude Cost and Raw Rows

Base catalog tables MUST deny all access to the `anon` role via Row-Level
Security. Public reads MUST happen only through views that omit the `cost`
column entirely.

#### Scenario: anon denied on base products table

- GIVEN the `anon` role
- WHEN it attempts `SELECT * FROM products`
- THEN the query MUST return zero rows or an authorization error, never
  `cost` data

#### Scenario: anon reads catalog via public view

- GIVEN published products and variants exist
- WHEN `anon` selects from the public catalog view keyed by `slug`
- THEN rows MUST be returned including `slug`, `name`, `color`, and `price`
- AND the `cost` column MUST NOT appear in the result set

### Requirement: Service Role Has Full Catalog Access

The `service_role` MUST have unrestricted read/write access to `products`,
`product_variants`, and `product_images` base tables.

#### Scenario: service_role reads cost and writes rows

- GIVEN the `service_role` role
- WHEN it selects from `products` including `cost`, and inserts a new variant
- THEN both operations MUST succeed

### Requirement: Soft-Delete Column On Products And Variants

The `products` table and the `product_variants` table MUST each carry a
soft-delete marker column (nullable timestamp, `NULL` meaning active) that
records retirement without removing the row.

#### Scenario: Soft-deleting a product marks it without removing the row

- GIVEN an active product row
- WHEN the product is soft-deleted
- THEN the row MUST remain present in `products` with its soft-delete
  column set
- AND the row MUST NOT be removed via `DELETE`

#### Scenario: Soft-deleting a variant marks it without removing the row

- GIVEN an active variant row
- WHEN the variant is soft-deleted
- THEN the row MUST remain present in `product_variants` with its
  soft-delete column set
- AND the row MUST NOT be removed via `DELETE`

### Requirement: Public Catalog Views Exclude Soft-Deleted Rows

The public catalog view(s) MUST filter out any product or variant whose
soft-delete column is set, in addition to the existing `cost`-omission and
RLS behavior already required.

#### Scenario: Soft-deleted product never appears in a public catalog read

- GIVEN a product soft-deleted via its soft-delete column
- WHEN `anon` selects from the public catalog view
- THEN no row for that product's `slug` MUST be returned, even though the
  underlying `products` row still exists

#### Scenario: Soft-deleted variant never appears in a public catalog read

- GIVEN a variant soft-deleted via its soft-delete column, on an
  otherwise-active product
- WHEN `anon` selects from the public catalog view
- THEN no row for that variant MUST be returned
- AND the product's other active variants MUST remain visible

### Requirement: Soft-Delete Never Touches stock_movements

Soft-deleting a product or a variant MUST be implemented as an `UPDATE` on
`products`/`product_variants` only. The `stock_movements` table, its `ON
DELETE RESTRICT` foreign key to `product_variants`, and its append-only
(no-UPDATE/DELETE) trigger MUST remain completely unchanged and unexercised
by soft-delete.

#### Scenario: Soft-deleting a variant with recorded stock movements leaves the ledger intact

- GIVEN a variant with existing `stock_movements` rows
- WHEN the variant is soft-deleted
- THEN every `stock_movements` row referencing that variant MUST remain
  unchanged
- AND no `DELETE` or `UPDATE` MUST be issued against `stock_movements`

#### Scenario: The FK RESTRICT and append-only trigger stay unexercised

- GIVEN the existing `ON DELETE RESTRICT` FK from
  `stock_movements.variant_id` to `product_variants.id` and its append-only
  trigger
- WHEN a product or variant is soft-deleted
- THEN neither the FK RESTRICT path nor the append-only trigger MUST fire,
  because no row in `stock_movements`, `product_variants`, or `products` is
  ever hard-deleted by this change
