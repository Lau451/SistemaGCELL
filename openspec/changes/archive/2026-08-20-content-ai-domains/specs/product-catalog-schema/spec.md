# Delta for Product Catalog Schema

## ADDED Requirements

### Requirement: Products Carry An Optional Short Description Column

The `products` table MUST carry a nullable `short_description` text
column, added as a purely additive migration with no default value
(metadata-only ALTER, no table rewrite). The public catalog view exposing
catalog products MUST include `short_description` without dropping or
narrowing the `anon`/`authenticated` read grant it already holds.

#### Scenario: Short_description defaults to null on existing rows

- GIVEN a product row that existed before this migration
- WHEN it is read after migration
- THEN `short_description` MUST be null, with no data loss to any other
  column

#### Scenario: Anon can still read the catalog view after the migration

- GIVEN the catalog view has been updated to expose `short_description`
- WHEN `anon` selects from it
- THEN the read MUST succeed exactly as before, now including
  `short_description`

#### Scenario: Cost omission and RLS remain unaffected

- GIVEN the schema change is applied
- WHEN `anon` or `service_role` access is exercised as in the existing
  cost-omission and RLS requirements
- THEN both MUST behave exactly as already specified, unaffected by this
  addition
