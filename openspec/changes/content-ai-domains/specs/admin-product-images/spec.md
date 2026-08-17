# Delta for Admin Product Images

## ADDED Requirements

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
