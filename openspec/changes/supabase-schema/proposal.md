# Proposal: Supabase Schema — Products, Variants, Stock, Photo Storage

## Intent

`supabase/` is `init`-only: `config.toml` and an empty `migrations/`. Nothing persists, so the public catalog and admin panel are both blocked. This change authors the real Postgres schema — the durable data contract every later adapter builds on — and separates public catalog reads from cost/stock data before any client touches the DB.

## Product Decisions (user-confirmed)

- **Stock auditing: required.** Buyer/admin needs to answer "why did this variant's stock change" (returns, breakage, restock reconciliation). This promotes stock from a quantity counter to an **append-only movements ledger** — reverses the proposal's original default; see updated Scope/Approach below.
- **Public stock visibility: boolean only.** The public catalog shows `in_stock` (available/not available), never an exact or approximate count. Confirmed as originally proposed.
- **Product identity in URLs: slug.** Public catalog routes use a human-readable, unique `slug` column (e.g. `/fundas-iphone-15`), not the raw UUID — SEO and shareability on WhatsApp/social. Decided now because retrofitting a slug after products exist needs a backfill migration.

## Scope

### In Scope
- Migrations for `products` (with `slug`, unique), `product_variants` (with `color`), `product_images`, and a `stock_movements` append-only ledger (per-variant running quantity derived from movement rows, not a mutable counter column).
- UUID surrogate PKs, FKs with explicit delete behaviour, invariants as SQL constraints (non-blank name/model/slug, non-negative price/cost, movement quantities enforce direction via `movement_type`).
- RLS + explicit GRANTs: base tables deny `anon`; public reads via views excluding `cost` and exact stock (exposing only a derived `in_stock` boolean computed from the ledger); writes via `service_role`.
- One public-read Storage bucket for product photos, writes `service_role`-only, declared in `config.toml`.
- `supabase/seed.sql` (already referenced by `config.toml`).

### Out of Scope
- **Python domain alignment** (`product.py` `id`/`color`/`slug`; `repository.py` `get_by_name` → `get_by_id`). Explicit fast-follow change: mixing a data-model change with an application-code change makes both harder to review and roll back independently.
- Postgres repository adapter; any DB client in `backend/pyproject.toml`.
- `content` / `ai` / `recommendation` tables — zero domain code exists, so schema now is speculative.
- Movement-reason taxonomy UI/reporting (e.g. an admin screen to browse ledger history) — the ledger table and its constraints are in scope; any admin UI to consume it is a later change.

## Capabilities

### New Capabilities
- `product-catalog-schema`: products (incl. slug), variants, images — keys, constraints, public exposure.
- `inventory-schema`: append-only stock movements ledger, derived `in_stock` boolean, public/admin visibility split.
- `product-media-storage`: photo bucket, public read, admin-only write.

### Modified Capabilities
- `platform-foundation`: its "Supabase CLI Wiring Without Schema" requirement asserts `migrations/` holds no schema SQL — this change supersedes it.

## Approach

**Naming**: carry forward the archived `initial-scaffolding` decision — `supabase migration new <snake_name>`, CLI timestamp prefix, no hand-numbering. Confirmed current, not re-litigated. Author dependency-first in one session: `products_catalog` → `inventory` → `public_catalog_rls` → `storage_product_photos`.

**RLS — recommended: public views over column GRANTs.** Postgres has no column-level RLS. Base tables get RLS with no `anon` policy; `anon` gets `GRANT SELECT` only on views omitting `cost` and exposing stock as a derived `in_stock` boolean. Preferred over base-table column `GRANT`/`REVOKE`: one self-documenting contract, no confusing partial failures on PostgREST `select=*`, one place for derived fields. `sdd-design` owns exact DDL.

**GRANTs are mandatory**: `auto_expose_new_tables` is off, so an omitted GRANT breaks the public catalog outright (empty/404) — not only a leak risk.

**Stock — append-only movements ledger (user-confirmed, not a counter).** Every stock change (restock, sale, return, breakage) is an inserted row (`variant_id`, `movement_type`, `quantity_delta`, `reason`, `created_at`); current stock is `SUM(quantity_delta)` per variant, not a mutable column — no `UPDATE`s to a quantity field, so the history is never lost. `sdd-design` owns the exact `movement_type` enum and whether the running total is a view/materialized view or computed on read.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `supabase/migrations/` | New | 4 CLI-generated migrations |
| `supabase/seed.sql` | New | Minimal local seed |
| `supabase/config.toml` | Modified | Product-photos bucket |
| `openspec/specs/platform-foundation/spec.md` | Modified | Supersede "no schema SQL" |
| `backend/src/gcell/products/**` | Unchanged | Deliberate — fast-follow |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| RLS leaks `cost`/exact stock | Med | Views exclude columns entirely; verify as `anon`, not by reading DDL |
| Missing GRANT breaks public catalog | Med | Grant checklist per table/view; verify a real `anon` read returns rows |
| Docker Desktop unverified on this host | Med | Confirm before apply; `supabase start`/`db reset` is now a hard dependency |
| Schema/domain drift until fast-follow | Med | Record the `id`/`color`/`slug`/`get_by_id` delta in the follow-up change |
| Ledger read cost grows unbounded over time | Low | `sdd-design` decides view vs. materialized/indexed running-total strategy; not a correctness risk at this data scale |
| Exceeds 400-line review budget | Med | Stacked slices: catalog+storage, then inventory(ledger)+RLS — ledger adds surface, watch this slice first |

## Rollback Plan

Nothing is deployed; no production data exists. Local: delete the migration files and `supabase db reset` to return to an empty DB. If already pushed remotely: one migration dropping views, tables (child-first), policies, and bucket restores the prior state — only seed data is lost. Backend and frontend are untouched, so no application rollback.

## Dependencies

- Docker Desktop running (for `supabase start` / `db reset`).
- Supabase CLI (already installed by `initial-scaffolding`).

## Success Criteria

- [ ] `supabase db reset` applies all migrations cleanly from empty.
- [ ] As `anon`: catalog views return rows keyed by `slug`; `cost` and exact stock unreachable, including via base tables.
- [ ] Inserting stock movement rows changes the derived `in_stock` boolean without any `UPDATE` to a quantity column; movement history is queryable via `service_role`.
- [ ] As `service_role`: full read/write succeeds.
- [ ] Photo bucket serves public reads, rejects `anon` writes.
- [ ] Both pinned test suites stay green — no application code modified.
