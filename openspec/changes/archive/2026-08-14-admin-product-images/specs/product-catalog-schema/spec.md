# Delta for Product Catalog Schema

## MODIFIED Requirements

### Requirement: Product Images Reference a Variant

`variant_id` on `product_images` MUST be nullable and, when set, MUST
reference an existing `product_variants` row via a foreign key. A `NULL`
`variant_id` is a valid, intentional state representing a product-level
hero image, not a data-integrity violation; the foreign key constraint
governs only the non-null case.

(Previously: "`product_images` MUST reference an existing
`product_variants` row via a foreign key and MUST NOT permit an image row
with no valid parent variant." That text contradicted the shipped,
already-live nullable `variant_id` column — corrected here as a
documentation-drift fix, not a behavior change, matching the same
drift-correction class as commit `f073d8c`.)

#### Scenario: Image insert without valid variant rejected
- GIVEN no variant exists with id `X`
- WHEN a `product_images` row is inserted referencing variant `X`
- THEN the insert MUST fail on the foreign key constraint

#### Scenario: Image insert with a null variant_id succeeds as a hero image
- GIVEN a product with no variant reference supplied
- WHEN a `product_images` row is inserted with `variant_id = NULL`
- THEN the insert MUST succeed
- AND the row MUST be treated as a valid product hero image, not an
  integrity error
