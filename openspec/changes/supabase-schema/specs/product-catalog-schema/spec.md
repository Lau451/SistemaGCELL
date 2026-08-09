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
