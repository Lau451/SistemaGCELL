# Delta for Product Persistence

## ADDED Requirements

### Requirement: Repository Port Exposes Image Read And Write Operations

The repository port MUST expose operations to insert an image row, delete
an image row by id, update `sort_order` for one or more images, and list
images for a product (including their `variant_id`, which MAY be `NULL`
for a hero image). Both the Postgres adapter and the in-memory adapter MUST
implement all image operations identically in observable behavior.

#### Scenario: Insert persists an image row with nullable variant_id
- GIVEN a product with at least one variant
- WHEN an image is inserted with `variant_id = NULL`
- THEN the row MUST persist and MUST be retrievable as a hero image for
  that product

#### Scenario: In-memory and Postgres adapters agree on image operations
- GIVEN the same sequence of insert, reorder, and delete image operations
- WHEN run against the in-memory adapter and the Postgres adapter
  separately
- THEN both adapters MUST produce the same observable final state
  (surviving rows, their `sort_order`, and their `variant_id`)

### Requirement: Images Of A Soft-Deleted Variant Are Hidden At Read Time

Listing a product's images MUST exclude any image whose `variant_id`
references a variant that has been soft-deleted (`deleted_at IS NOT NULL`),
mirroring the read-time soft-delete cascade already applied to variant rows
themselves. The composite foreign key on `product_images` does not cascade
on soft delete (no row is actually deleted), so this filtering MUST happen
in the read query, not rely on the database removing the row. Hero images
(`variant_id IS NULL`) are unaffected by variant soft-delete.

#### Scenario: Retiring a variant hides its images from the product's image list
- GIVEN a variant with two images and a sibling variant with one image
- WHEN the first variant is soft-deleted (retired)
- THEN listing the product's images MUST return only the sibling variant's
  image and any hero images
- AND the retired variant's image rows and Storage objects MUST still exist
  unchanged (no purge)

#### Scenario: Hero images remain listed regardless of variant state
- GIVEN a product with a hero image (`variant_id = NULL`) and a retired
  variant with its own image
- WHEN the product's images are listed
- THEN the hero image MUST be included
- AND the retired variant's image MUST NOT be included

### Requirement: Image Insert And Delete Do Not Touch Product Or Variant Rows

Inserting or deleting a `product_images` row MUST NOT modify any
`products` or `product_variants` row, and MUST NOT require an active
transaction spanning those tables beyond the image write itself.

#### Scenario: Deleting an image leaves its variant and product untouched
- GIVEN a variant with one image
- WHEN the image is deleted via the repository port
- THEN the variant row and its parent product row MUST remain unchanged
