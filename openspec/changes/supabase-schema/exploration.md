# Exploration: supabase-schema

Designing and implementing the real Postgres schema on top of the `supabase init`-only scaffold from `initial-scaffolding`.

## Current State

- `supabase/` contains only `config.toml` (from `supabase init`) and `.gitignore` — no `supabase/migrations/` directory, no schema SQL, no `seed.sql` file (though `config.toml`'s `db.seed.sql_paths = ["./seed.sql"]` references one that doesn't exist yet).
- `config.toml`: `api.schemas = ["public", "graphql_public"]`, `auto_expose_new_tables` is commented out (defaults to NOT auto-exposed — current CLI's "new cloud default"), meaning every new table needs explicit `GRANT`s or PostgREST won't serve it at all. `db.major_version = 17`. `storage.enabled = true`, `file_size_limit = "50MiB"`, no buckets configured (only a commented-out example). `db.migrations.schema_paths = []` (declarative-schema mode not used — CLI-generated migration files is the active mode).
- `backend/src/gcell/products/domain/product.py` has REAL code: `Product` (`name: str`, `variants: list[ProductVariant]`) and `ProductVariant` (`phone_model: str`, `price: float`, `cost: float`), pure dataclasses with `__post_init__` invariants (non-blank name/phone_model, non-negative price/cost). **Neither has an `id`/UUID field.** No `color` field despite the business description mentioning "phone model, color" variants. No stock/quantity field, no SKU, no image reference field.
- `backend/src/gcell/products/application/repository.py`: `ProductRepository` Protocol port has `add`, `get_by_name`, `list_all` — product identity today is the **name string** (natural key), not a surrogate id. `RegisterProductUseCase` enforces uniqueness via `get_by_name`.
- `backend/src/gcell/products/infrastructure/in_memory_product_repository.py`: dict keyed by `product.name` — confirms name-as-key today.
- `backend/pyproject.toml` has **zero DB/Supabase client dependencies** (no `supabase-py`, `asyncpg`, `sqlalchemy`, `psycopg`). Confirms wiring a real Postgres-backed repository adapter into the FastAPI backend is NOT part of the existing scaffold and is a separate future change from pure schema/SQL authoring.
- `stock/`, `content/`, `ai/`, `recommendation/` domains have only empty `__init__.py` files in all three layers (`domain/application/infrastructure`) — zero real code exists for those domains to reconcile a schema against.
- The archived `initial-scaffolding` change's `design.md` **already resolved** the migration-naming question: "Decision: Supabase migration naming = CLI default, not `0001-0004`" — chosen approach is `supabase migration new <snake_name>` → `supabase/migrations/<YYYYMMDDHHMMSS>_<name>.sql`, explicitly rejecting hand-numbered `0001_*.sql` because "the CLI does not generate it, ordering breaks across branches, and `db diff`/`db push` fight it." That design doc also left a **draft content mapping** (never executed — no files exist):

  | Chat shorthand | `migration new` name | Contents |
  |---|---|---|
  | 0001 | `products_catalog` | products + variants + images |
  | 0002 | `stock_movements` | stock + movements |
  | 0003 | `content_styles` | content + styles |
  | 0004 | `rls_public_views` | RLS policies + public views |

  This mapping is a plan artifact, not a commitment — this change should confirm or revise it based on the actual chosen scope.
- WebSearch confirms current Supabase CLI docs: `supabase migration new` still always generates `<YYYYMMDDHHMMSS>_<description>.sql`; there is no CLI flag to force custom/sequential numbering — migrations are ordered purely by filename (timestamp) sort. So the prior design decision stands and is current.
- WebSearch on RLS patterns confirms: Postgres/Supabase has **no native column-level RLS**. The two practical patterns for a public-read/admin-write catalog with sensitive columns (cost, exact stock) are: (a) a `public` schema **view** that excludes sensitive columns, with `GRANT SELECT` to `anon` on the view only (base table RLS denies `anon` entirely), or (b) native Postgres column-level `GRANT`/`REVOKE` privileges (not RLS-specific) to restrict which columns `anon` can read directly. Admin/write operations should go through `service_role` (bypasses RLS) from the backend, never through client-side `anon`/`authenticated` roles.
- Prior change's risk log flagged "Docker Desktop unverified on this Windows host" and explicitly kept `supabase start` (local Postgres via Docker) out of scope. This change likely needs `supabase start` + `supabase db reset` to actually test migrations locally, so Docker availability becomes a real dependency now, not a deferred one.

## Affected Areas

- `supabase/config.toml` — already wired; may need a `[storage.buckets.*]` section uncommented if product-photo storage is in this change's scope.
- `supabase/migrations/` — does not exist yet; created by this change via `supabase migration new <name>` (timestamp-prefixed files, per already-decided convention).
- `supabase/seed.sql` — referenced by `config.toml` but does not exist; needed only if local dev/test seed data is desired.
- `backend/src/gcell/products/domain/product.py` — schema must be consistent with (or this file must be extended to match) `Product`/`ProductVariant`; currently missing `id`/UUID and `color`. Open question for propose/design: is domain-code alignment in THIS change's scope, or a strict SQL-only change with domain-code alignment deferred?
- `backend/src/gcell/products/application/repository.py` — `ProductRepository` port shape (`get_by_name` as the identity lookup) implies a natural-key model today; a UUID-surrogate-key schema decision would eventually require this port's signature to change (e.g. `get_by_id`), which is out of scope for a SQL-only change but worth flagging now so the port isn't redesigned twice.
- `backend/pyproject.toml` — no DB client dependency; explicitly NOT modified by a schema-only change (wiring a real repository adapter to Postgres is a separate future change).
- `openspec/changes/archive/2026-08-09-initial-scaffolding/design.md` — source of the already-made migration-naming decision and the draft 0001-0004 content-mapping plan that this change should confirm/revise for actual scope.

## Approaches

### 1. Minimal — products + variants only
Tables: `products`, `product_variants`; maybe `product_images`.
- Pros: smallest surface, directly matches existing domain code today, fastest to ship/test, unblocks a real `ProductRepository` SQL adapter soonest.
- Cons: stock/inventory (explicitly named in the topic as core scope: "stock/pricing/costs") stays unmodeled; admin panel work for stock/content blocked longer.
- Effort: Low.

### 2. Medium — products + variants + stock/inventory
Adds a stock/inventory table (e.g. simple per-variant quantity counter or a movements ledger).
- Pros: covers the two domains most explicitly named in the topic description; matches the draft 0001+0002 mapping; lets an admin stock-adjustment MVP start right after.
- Cons: doubles the sensitive-data RLS surface in one change (cost AND exact stock counts both need public/admin separation at once); stock semantics (simple counter vs. append-only movements ledger) is itself an undecided design question that could expand this change's scope unexpectedly.
- Effort: Medium.

### 3. Full — products + variants + stock + content/AI + publication history
Everything named in the topic in one change.
- Pros: one coherent schema pass, avoids re-doing migration/RLS design later.
- Cons: `content`/`ai` domains have **zero existing code** (only `__init__.py` stubs) — no decided data contract for what an "AI-generated social post" record even contains (provider, prompt, image ref, platform, status?), so this schema would be speculative; large single-change blast radius against the 400-line review budget; RLS design must correctly gate 4+ sensitive concerns simultaneously, raising misconfiguration risk.
- Effort: High.

## Recommendation

Medium (products + variants + stock) as the target scope for this change, explicitly deferring content/AI tables to a later change (they have no real domain code yet, so any schema now would be speculative). Storage bucket + policy for product photos should likely be included in this change (thin: one public-read bucket, admin-only writes via `service_role`) since the public catalog needs image references from day one — but this is a scope question for the user to confirm in `sdd-propose`, not decided here. If Medium risks exceeding the review budget, recommend chaining products+variants as PR #1 and stock as a stacked PR #2 within the same change, rather than dropping to Minimal outright.

## Risks

- RLS misconfiguration exposing cost/stock data publicly: Postgres has no native column-level row security; must combine base-table RLS (deny `anon` SELECT, or restrict via a public view) with explicit column `GRANT`/`REVOKE` or a dedicated public view excluding `cost` and exact stock counts — easy to get wrong by exposing the base table via PostgREST with a permissive `USING (true)` policy that still returns sensitive columns.
- `auto_expose_new_tables` defaults to unset/false in current CLI — every new table needs explicit `GRANT` statements in the migration or PostgREST will silently return empty/404 for the public catalog, not just leak data the other direction.
- Migration ordering: CLI timestamp-prefix ordering means all migration files for this change must be authored in strict chronological sequence (products before variants-FK before stock-FK before RLS-policies) within one working session via `supabase migration new`, or `db push`/`db diff` could apply them out of intended order.
- No confirmed Docker Desktop availability on this Windows host (flagged in the prior change, `supabase start` was explicitly deferred) — this change likely needs `supabase start` + `supabase db reset` to test migrations locally before merge, making Docker a new hard dependency, not an optional one.
- Domain/schema drift: `Product`/`ProductVariant` have no `id` field and no `color` field, and identity is currently by `name` (natural key) in the repository port — schema design must decide surrogate UUID PK vs. natural key, and whether backend domain-code changes are in this SDD change's scope or a strictly separate SQL-only change (recommend SQL-only here, flag domain alignment as fast-follow, but this is a decision for the user).
- Content/AI domain has zero existing code — reinforces deferring those tables regardless of chosen scope option, independent of the review-budget argument.

## Ready for Proposal

Yes — with two explicit open decisions the orchestrator should surface to the user before `sdd-propose`: (1) exact scope — Minimal / Medium / Full per the options above (Medium recommended), and (2) whether Supabase Storage bucket/policy setup for product photos is included in this change or deferred to a later one.
