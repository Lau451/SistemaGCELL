# Design: Supabase Schema — Products, Variants, Stock Ledger, Photo Storage

## Technical Approach

Four CLI-timestamped migrations, dependency-first, plus `supabase/seed.sql` and one `config.toml` bucket block. Four base tables (`products`, `product_variants`, `product_images`, `stock_movements`) are private: RLS enabled with **zero** policies for `anon`/`authenticated`. All public reads go through `SECURITY DEFINER` views that never select `cost` and never select stock quantity — only a derived `in_stock` boolean. This supersedes the archived `platform-foundation` requirement "Supabase CLI Wiring Without Schema"; real schema SQL is now authorized in `supabase/migrations/`.

**Verified**: `auto_expose_new_tables` is commented out in `supabase/config.toml:24`, and its own doc comment states unset ⇒ entities are **NOT** auto-exposed. Consequence: every table **and every view** needs an explicit `GRANT` — including for `service_role`, not just `anon`. A missing GRANT is a hard 404/empty, not a silent leak.

## Architecture Decisions

| # | Decision | Choice | Rejected | Rationale |
|---|---|---|---|---|
| 1 | Public column hiding | Views + GRANT on view only | Base-table column `GRANT`/`REVOKE` | One self-documenting contract; no partial failure on `select=*`; one home for derived fields |
| 2 | View security mode | Default `security_invoker = off` (definer, owner `postgres`) | `security_invoker = on` | Invoker mode would force base-table privileges back onto `anon`, defeating Decision 1. The view **is** the boundary. Supabase's `security_definer_view` linter warning is expected and intentional |
| 3 | `movement_type` domain | `text` + named `CHECK` in (`restock`,`sale`,`return`,`breakage`,`adjustment`) | Native `CREATE TYPE ... AS ENUM` | A CHECK is edited by ordinary `ALTER TABLE` in a migration; enum values cannot be removed and reordering needs a type rewrite. A small shop will add reasons later |
| 4 | Current stock | Live `SUM(quantity_delta)` in internal view `variant_stock_levels`, backed by covering index | Materialized view; trigger-maintained counter | A stale `in_stock` causes overselling — a real business bug. At this volume the aggregate is sub-millisecond. The internal view is the single swap point if volume ever justifies a rollup |
| 5 | `in_stock` derivation | `COALESCE(sl.quantity_on_hand, 0) > 0` | `sl.quantity_on_hand > 0` | LEFT JOIN yields NULL for a variant with zero movements; without COALESCE it renders NULL, not `false` |
| 6 | Append-only enforcement | `GRANT SELECT, INSERT` only (no UPDATE/DELETE) **plus** a `BEFORE UPDATE OR DELETE` trigger that raises | GRANT-level only | GRANTs do not bind a direct `postgres` connection. The trigger makes append-only a schema invariant; it is droppable in a later migration if a data repair is ever needed |
| 7 | Ledger FK delete rule | `stock_movements.variant_id ... ON DELETE RESTRICT` | `CASCADE` | An audit ledger that cascades away is not an audit ledger. Deleting a variant with history must be an explicit business act (soft-delete is a later change) |
| 8 | `slug` | `NOT NULL UNIQUE` + `CHECK (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$')` + length 1..80 | Format enforced only in Python | This change owns the column; generation stays a fast-follow. A DB-level check is a cheap net that keeps a malformed slug from ever reaching a URL, wherever generation lands |
| 9 | Money type | `numeric(10,2)` | `double precision` (mirrors domain `float`) | Deliberate divergence from `product.py`; the fast-follow should move Python to `Decimal` |
| 10 | Image ownership | `product_id NOT NULL` + `variant_id NULL`, composite FK | Separate product/variant image tables | NULL variant = product hero, non-NULL = colour-specific. MATCH SIMPLE skips the composite FK when `variant_id` is NULL, so one nullable column covers both and still forbids cross-product variants |
| 11 | Storage writes | Bucket `public = true`, **zero** write policies | An explicit `service_role` INSERT policy | `service_role` bypasses `storage.objects` RLS; a write policy would be dead code implying `anon` writes were ever considered |

Decision 10 is the one non-obvious shape:

```sql
ALTER TABLE product_variants ADD CONSTRAINT product_variants_product_id_id_key UNIQUE (product_id, id);
ALTER TABLE product_images ADD CONSTRAINT product_images_variant_fk
  FOREIGN KEY (product_id, variant_id) REFERENCES product_variants (product_id, id) ON DELETE CASCADE;
```

## Data Flow

```
anon (Next.js (public))  ──→ PostgREST ──→ catalog_products / catalog_variants
                                              / catalog_product_images     [GRANT SELECT to anon]
                                                     │ security definer (owner: postgres)
                                                     ▼
                                           variant_stock_levels  [no anon GRANT]
                                                     │
service_role (FastAPI (admin)) ──→ PostgREST ──→ base tables  [RLS on, 0 anon policies]
                                                     ▲
                              INSERT-only ledger ────┘  stock_movements
public browser ──→ Storage CDN ──→ bucket product-photos (public read, service_role write)
```

Exposed columns: `catalog_products` (id, slug, name, description, created_at); `catalog_variants` (id, product_id, phone_model, color, price, `in_stock`); `catalog_product_images` (id, product_id, variant_id, storage_path, alt_text, sort_order). `cost` and `quantity_on_hand` appear in no public view.

## File Changes

| File | Action | Description |
|---|---|---|
| `supabase/migrations/<ts>_products_catalog.sql` | Create | 1. `products` (uuid PK, slug + checks), `product_variants` (color, numeric price/cost), `product_images`, composite FK, `set_updated_at()` trigger fn |
| `supabase/migrations/<ts>_stock_movements_ledger.sql` | Create | 2. Ledger table, `movement_type` CHECK, per-type sign-direction CHECK, `quantity_delta <> 0`, covering index `(variant_id) INCLUDE (quantity_delta)`, append-only trigger |
| `supabase/migrations/<ts>_public_catalog_rls.sql` | Create | 3. `ENABLE ROW LEVEL SECURITY` on all 4 tables (no anon policies), `variant_stock_levels`, 3 catalog views, **all** GRANTs (base tables → `service_role`; catalog views → `anon`, `authenticated`) |
| `supabase/migrations/<ts>_storage_product_photos.sql` | Create | 4. Idempotent `insert into storage.buckets ... on conflict (id) do nothing`, one `anon` SELECT policy for API listing, zero write policies |
| `supabase/seed.sql` | Create | 2 products, ~4 variants, images, restock movements — enough to prove `in_stock` both ways |
| `supabase/config.toml` | Modify | `[storage.buckets.product-photos]`: `public = true`, `file_size_limit = "5MiB"`, jpeg/png/webp |
| `supabase/tests/rls_checks.sql` | Create | psql assertion script (see Testing) |
| `backend/src/gcell/products/**` | Unchanged | Deliberate — fast-follow |

Sign direction (migration 2): `restock`/`return` ⇒ `quantity_delta > 0`; `sale`/`breakage` ⇒ `< 0`; `adjustment` ⇒ either.

## Testing Strategy

| Layer | What | Approach |
|---|---|---|
| Schema | All migrations apply clean from empty | `supabase db reset` (requires Docker Desktop — unverified on this host) |
| Security | `anon` cannot reach base tables; views expose no `cost`/quantity | `supabase/tests/rls_checks.sql`: `SET ROLE anon` + expected-failure asserts, then column-list assert on each view |
| Behaviour | `in_stock` flips via INSERT only | Insert `sale` movements to net zero; assert `in_stock = false` with no UPDATE issued; assert UPDATE/DELETE on `stock_movements` raises |
| Regression | App code untouched | `npm --prefix frontend test` and `uv run --project backend pytest -q` stay green |

Strict TDD applies as RED-first assertion scripts: `rls_checks.sql` is authored before the migrations and must fail on the empty DB. **pgTAP / `supabase test db` was rejected for this change** — it needs `create extension pgtap` in a shipped migration; plain psql asserts add no extension. Adopting pgTAP is a candidate follow-up.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. `supabase migration new` is a developer workflow command, not shipped code.

## Migration / Rollout

No data migration — the database is empty and nothing is deployed. Local rollback is `supabase db reset` after deleting the migration files. Ordering is enforced by authoring all four via `supabase migration new` in one session so CLI timestamps are strictly ascending.

## Open Questions

- [ ] Docker Desktop availability on this Windows host — a hard blocker for `supabase db reset`, so it must be confirmed before `sdd-apply`, not during.
- [ ] `variant_stock_levels` lives in `public` with no `anon` GRANT. A dedicated non-exposed schema would be stronger defence-in-depth; rejected here for config churn, but revisit if more internal views appear.
