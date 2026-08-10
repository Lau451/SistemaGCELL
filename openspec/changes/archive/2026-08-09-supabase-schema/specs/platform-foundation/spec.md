# Delta for platform-foundation

## MODIFIED Requirements

### Requirement: Supabase CLI Wiring Without Schema

The repository MUST include `supabase init` wiring, and `supabase/migrations/`
MUST contain the real product-catalog, inventory, RLS, and storage schema
authored by the `supabase-schema` change, applied dependency-first via
CLI-generated migration files.
(Previously: asserted `migrations/` MUST contain no schema SQL files at all —
that constraint is superseded now that the catalog/inventory/storage schema
exists.)

#### Scenario: Config exists, migrations contain real schema

- GIVEN the `supabase/` directory after this change
- WHEN `supabase/config.toml` and `supabase/migrations/` are inspected
- THEN `config.toml` MUST exist AND `migrations/` MUST contain the
  CLI-generated catalog, inventory, RLS, and storage migration files

#### Scenario: Fresh database reset applies all schema cleanly

- GIVEN an empty local Supabase database
- WHEN `supabase db reset` runs
- THEN all migrations MUST apply in dependency order with no errors, leaving
  `products`, `product_variants`, `product_images`, `stock_movements`, their
  public views, and the product-photos bucket in place
