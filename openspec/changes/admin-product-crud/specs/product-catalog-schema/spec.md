# Delta for Product Catalog Schema

## ADDED Requirements

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
