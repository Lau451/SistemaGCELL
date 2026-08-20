# Admin AI Content Authoring Specification

## Purpose

The `content` domain's admin-triggered generation use cases: one call
producing both product-copy fields (D10), and a separate alt-text
generation call — both draft-only with zero write side effect (D5),
on-demand and single-item (D6).

## Requirements

### Requirement: Generate Copy Returns Both Fields From One Gemini Call

A single "generate copy" action MUST invoke Gemini exactly once and MUST
return both `short_description` and `description` as a draft pair. There
MUST NOT be two separate calls or two separate actions for the two fields.

#### Scenario: One click yields both draft fields

- GIVEN an admin viewing an existing product with name, model, and variant
  colors
- WHEN the admin triggers "generate copy"
- THEN exactly one Gemini call MUST be made
- AND the response MUST include a draft `short_description` and a draft
  `description`

### Requirement: Generate Alt Text Is A Separate, Image-Input Action

Generating alt text for a product photo MUST be a distinct action from
generate-copy, MUST send that photo as image input to Gemini, and MUST
target exactly one existing image at a time.

#### Scenario: Alt text generation targets one image

- GIVEN an admin viewing an existing product image
- WHEN the admin triggers "generate alt text" for that image
- THEN exactly one Gemini image-input call MUST be made for that image
- AND the response MUST be a draft `alt_text` string, applied to no other
  image

### Requirement: Generate Calls Have Zero Write Side Effect

Neither generate-copy nor generate-alt-text MUST write to any database
table or storage object. Both MUST return a draft the admin can edit before
an explicit, separate save action persists it.

#### Scenario: Generating copy does not persist anything

- GIVEN a product with an existing `description`
- WHEN the admin triggers generate-copy and does not save
- THEN the persisted `description` and `short_description` MUST be
  unchanged

#### Scenario: Generating alt text does not persist anything

- GIVEN an image with existing `alt_text`
- WHEN the admin triggers generate-alt-text and does not save
- THEN the persisted `alt_text` MUST be unchanged

### Requirement: Generation Is On-Demand, Admin-Authenticated, Single-Item

Every generate route MUST require the existing admin JWT guard, MUST act on
exactly one product or one image per call, and MUST NOT be reachable from
any bulk, automatic (create/upload-triggered), or public/unauthenticated
path.

#### Scenario: No bulk generate route exists

- GIVEN the set of AI-backed admin routes
- WHEN inspected
- THEN none MUST accept more than one product id or image id per request

#### Scenario: Upload does not auto-trigger alt-text generation

- GIVEN an admin uploads a new product image
- WHEN the upload completes
- THEN no Gemini call MUST be made automatically

### Requirement: Generation Excludes Price From The Prompt

The generate-copy prompt input MUST NOT include a variant's price or cost;
it MAY include name, model, and variant colors.

#### Scenario: Price is absent from the generation input

- GIVEN a product with variants of different prices
- WHEN generate-copy builds its Gemini request
- THEN no price or cost value MUST appear in the request payload

### Requirement: Content Never Persists Products Or Images Directly

`content` MUST NOT issue SQL against `products` or `product_images` tables
and MUST NOT own a repository for them; the save step that persists a
draft MUST go through the `products` domain's existing write path.

#### Scenario: Content has no products repository

- GIVEN the `content` domain's application layer
- WHEN its dependencies are inspected
- THEN it MUST depend on `ai`, and on `products` only for the save step —
  it MUST NOT own persistence itself
