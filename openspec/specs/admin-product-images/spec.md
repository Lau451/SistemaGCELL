# Admin Product Images Specification

## Purpose

Admin write path for product images: upload, replace, delete, reorder, and
hero/variant assignment, with server-side validation and IDOR-safe ownership
checks at the use-case layer.

## Requirements

### Requirement: Image Upload Is Rejected Without Admin Authorization

Every image write use case (upload, delete, reorder, reassign) MUST run only
after `verify_admin_jwt` passes on the `/admin` router, with no separate or
weaker check.

#### Scenario: Upload without a JWT is rejected
- GIVEN a multipart upload request to an admin image endpoint with no
  `Authorization` header
- WHEN the request reaches the `/admin` router
- THEN the request MUST be rejected with `401 Unauthorized`
- AND no Storage write and no `product_images` insert MUST occur

### Requirement: Image Ownership Is Checked At The Use-Case Layer

Every image operation targeting an existing image or variant id MUST resolve
that id through a use-case-layer ownership scan against the addressed
product before any repository mutation. Route handlers MUST NOT trust a
caller-supplied product id paired with an image/variant id belonging to a
different product; the use case MUST verify the parent chain itself.

#### Scenario: Image belonging to another product is not found
- GIVEN product `A` and product `B` each have at least one image
- WHEN an admin issues a delete/replace/reorder request for product `A`
  referencing an image id that actually belongs to product `B`
- THEN the use case MUST return not-found
- AND the response MUST be `404`, never a `403` that confirms the image
  exists, and never a successful mutation

#### Scenario: Variant belonging to another product is not found on assignment
- GIVEN product `A` and product `B` each have at least one variant
- WHEN an admin assigns an image on product `A` to a `variant_id` that
  belongs to product `B`
- THEN the use case MUST reject with not-found before any Storage or DB
  write

### Requirement: Upload Validation Runs Before Any Storage Write

An uploaded file MUST be validated against the bucket-legal mime types
(jpeg, png, webp) and the 5MiB size ceiling before any Storage `put` call or
`product_images` insert is attempted. A file failing either check MUST be
rejected with a client error and MUST leave no Storage object and no DB row.

#### Scenario: Disallowed mime type is rejected before Storage
- GIVEN a file with mime type `application/pdf`
- WHEN it is submitted to the upload endpoint
- THEN the request MUST be rejected with `422 Unprocessable Entity`
- AND no Storage `put` call MUST be made

#### Scenario: Oversized file is rejected before Storage
- GIVEN a file exceeding 5MiB
- WHEN it is submitted to the upload endpoint
- THEN the request MUST be rejected with `422 Unprocessable Entity`
- AND no Storage `put` call MUST be made

#### Scenario: Valid file within limits proceeds to normalization
- GIVEN a jpeg file under 5MiB
- WHEN it is submitted to the upload endpoint
- THEN validation MUST pass and normalization MUST run

### Requirement: Uploaded Images Are Server-Side Normalized

Every accepted upload MUST be resized/recompressed server-side so the stored
object satisfies the bucket's mime and size constraints, regardless of the
source image's original dimensions or encoding, before the Storage `put`
call.

#### Scenario: Oversized source image is resized before storing
- GIVEN a valid-mime source image wider than the bucket's practical serving
  size
- WHEN it is uploaded
- THEN the stored object MUST be resized/recompressed to fit within the
  5MiB, jpeg/png/webp constraint
- AND the resulting object, not the original bytes, MUST be what is written
  to Storage

#### Scenario: Normalization failure aborts before any write
- GIVEN a file that passes mime/size validation but fails to decode/process
  (e.g. corrupt image data)
- WHEN normalization is attempted
- THEN the request MUST be rejected with a client error
- AND no Storage `put` call and no `product_images` insert MUST occur

### Requirement: Successful Upload Persists Both Storage Object And DB Row, With Compensation On Partial Failure

A successful upload MUST result in both a Storage object and a
`product_images` row existing. If the DB insert fails after the Storage
object was written, the use case MUST issue a compensating delete of that
Storage object before returning an error, so no orphan object is left behind
by a normal request-scoped failure.

#### Scenario: Insert failure after successful Storage write triggers compensation
- GIVEN normalization succeeded and the object was written to Storage
- WHEN the subsequent `product_images` insert fails
- THEN the use case MUST delete the just-written Storage object before
  returning the error
- AND no orphan object MUST remain reachable by the client-visible outcome

#### Scenario: Successful upload leaves matching Storage object and row
- GIVEN a valid, in-limit image
- WHEN the upload use case completes successfully
- THEN exactly one Storage object and one `product_images` row MUST exist,
  linked by `storage_path`

### Requirement: Delete Is Hard, Row-First-Then-Storage, Tolerating A Missing Object

Deleting an image MUST remove both the `product_images` row and its Storage
object. The DB row MUST be deleted first; the Storage object deletion MUST
follow and MUST tolerate a 404/not-found response from Storage (already
missing object) as success, since the row's removal is what determines the
image's existence from the client's perspective.

#### Scenario: Delete removes both row and object
- GIVEN an existing image with a matching Storage object
- WHEN an admin deletes it
- THEN the `product_images` row MUST no longer exist
- AND the Storage object MUST no longer exist

#### Scenario: Delete tolerates an already-missing Storage object
- GIVEN an existing `product_images` row whose Storage object was already
  removed out of band
- WHEN an admin deletes the image
- THEN the row deletion MUST succeed
- AND a Storage 404 on the object delete MUST NOT surface as a failure to
  the caller

### Requirement: Replace Is Delete-Then-Upload Semantics

Replacing an image MUST behave as a hard delete of the prior Storage object
and row followed by the same validated upload/normalization path as a new
image, preserving the existing `sort_order` and `variant_id` (hero or
variant) unless explicitly changed by the caller.

#### Scenario: Replacing an image keeps its position and assignment
- GIVEN an existing image at `sort_order = 2` assigned to variant `V`
- WHEN an admin replaces its file without changing position or assignment
- THEN the new object MUST persist at the same `sort_order` and
  `variant_id`
- AND the prior Storage object MUST no longer exist

### Requirement: Reorder Replaces The Product's Whole Image Order In One Call

Reordering MUST accept the full ordered list of a product's image ids in a
single request and persist `sort_order` for the entire list, not a single
hero/variant group. The submitted list MUST be exactly a permutation of the
product's current image ids: any id missing from the product, any id
repeated, or the list omitting an id that belongs to the product MUST be
rejected as not-found, scoped by the same use-case-layer ownership check as
other image operations, without touching Storage.

#### Scenario: Reorder persists new sequence across groups
- GIVEN a product with images spanning its hero slot and two variants,
  currently at `sort_order` 0, 1, 2, 3
- WHEN an admin submits the full list of that product's image ids in a new
  order
- THEN the persisted `sort_order` values MUST reflect the new sequence on
  the next read
- AND no Storage object MUST be modified

#### Scenario: Reorder list containing a foreign image id is rejected
- GIVEN a product `A` with two images and product `B` with one image
- WHEN an admin submits a reorder list for product `A` that includes one of
  product `B`'s image ids
- THEN the request MUST be rejected as not-found
- AND no `sort_order` value MUST change

#### Scenario: Reorder list missing one of the product's own images is rejected
- GIVEN a product with three images
- WHEN an admin submits a reorder list containing only two of them
- THEN the request MUST be rejected as not-found
- AND no `sort_order` value MUST change

### Requirement: Hero Assignment Uses A Null Variant Id

An image MAY be assigned as a product hero image by setting its
`variant_id` to `NULL`; a hero image is not an error state and is not
required to reference any variant. An image MAY instead be assigned to a
specific variant of the same product by setting `variant_id` to that
variant's id.

#### Scenario: Uploading with no variant selected creates a hero image
- GIVEN an admin uploads an image without selecting a variant
- WHEN the upload completes
- THEN the persisted row MUST have `variant_id = NULL`
- AND the image MUST be treated as the product's hero image

#### Scenario: Uploading with a variant selected creates a variant image
- GIVEN an admin uploads an image and selects one of the product's own
  variants
- WHEN the upload completes
- THEN the persisted row MUST have `variant_id` set to that variant's id

### Requirement: Validation Failures Surface Actionable Feedback

A rejected upload (mime, size, or normalization failure) MUST return a
response body identifying which constraint failed, sufficient for the admin
UI to render a specific, non-generic error message.

#### Scenario: Mime rejection message names the constraint
- GIVEN a disallowed-mime upload is rejected
- WHEN the response is inspected
- THEN it MUST indicate the mime/size constraint that failed, not a generic
  500-style message

### Requirement: Alt Text Is Editable After Upload

An existing image's `alt_text` MUST be updatable independently of
re-uploading the image file. The update path MUST run behind the same
admin JWT guard and the same use-case-layer ownership check already
required for other image operations — an alt-text update targeting an
image belonging to a different product MUST be rejected not-found, never a
successful mutation.

#### Scenario: Admin updates alt text on an existing image

- GIVEN an existing image with `alt_text` `""`
- WHEN the admin submits a new `alt_text` value for it
- THEN the persisted `alt_text` MUST equal the new value
- AND no other field of that image row MUST change

#### Scenario: Alt-text update on another product's image is rejected

- GIVEN product `A` and product `B` each have an image
- WHEN an admin issues an alt-text update for product `A` referencing an
  image that belongs to product `B`
- THEN the request MUST be rejected not-found
- AND `alt_text` MUST NOT change on either image

#### Scenario: Unauthenticated alt-text update is rejected

- GIVEN a request to update `alt_text` with no `Authorization` header
- WHEN it reaches the endpoint
- THEN it MUST be rejected `401`
- AND `alt_text` MUST NOT change
