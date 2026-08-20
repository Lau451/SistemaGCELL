# Delta for Admin Product Management

## ADDED Requirements

### Requirement: Product Create And Edit Carry Description And Short Description

The admin product create and edit forms MUST expose an editable long
`description` field and an editable `short_description` field. Both MUST
be optional, hand-typeable, and independent of whether Gemini is
configured — a product MUST be creatable and editable with both fields
blank.

#### Scenario: Product is created with only manually typed copy

- GIVEN `GEMINI_API_KEY` is unset
- WHEN the admin submits a valid product with `description` and
  `short_description` typed by hand
- THEN the product MUST persist with both fields exactly as typed

#### Scenario: Product is creatable with both fields blank

- GIVEN a valid product submission with `description` and
  `short_description` omitted
- WHEN the form is submitted
- THEN the product MUST persist with both fields null

#### Scenario: Editing updates both fields independently

- GIVEN an existing product with a `description` and no
  `short_description`
- WHEN the admin edits only `short_description`
- THEN `short_description` MUST persist as edited
- AND `description` MUST remain unchanged
