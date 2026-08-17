# Delta for Public Catalog UI

## ADDED Requirements

### Requirement: Catalog Listing Renders The Short Description Blurb

When a product's `short_description` is set, the catalog listing MUST
render it alongside image, name, and price. When `short_description` is
null, the listing MUST render without it and MUST NOT show a
broken/empty placeholder.

#### Scenario: Listing renders the blurb when present

- GIVEN a product with a non-null `short_description`
- WHEN it renders on the catalog listing
- THEN its `short_description` text MUST be visible on the listing card

#### Scenario: Listing renders cleanly when the blurb is absent

- GIVEN a product with a null `short_description`
- WHEN it renders on the catalog listing
- THEN the card MUST render without error and without an empty/broken
  placeholder for the blurb
