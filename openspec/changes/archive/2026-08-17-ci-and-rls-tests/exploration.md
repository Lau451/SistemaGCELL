## Exploration: ci-and-rls-tests (CI pipeline + RLS integration tests)

### Current State

**Gap 1 — CI**: Confirmed absent from scratch — no `.github/workflows/`, no other CI config anywhere. This is the project's first CI pipeline.
- Backend commands available: `uv run pytest` (`backend/pyproject.toml`, testpaths=`tests`, `asyncio_mode=auto`), `uv run ruff check` (select `E,F,I,UP`), `uv run ruff format --check` (formatter configured but never invoked anywhere today). No Python typecheck tool configured (no mypy/pyright).
- Frontend commands (`frontend/package.json`): `npm run lint` (eslint flat config), `npm test` (`vitest run`), `npm run build` (`next build --webpack`). No dedicated typecheck script — `next build` fails on TS errors by default so it doubles as the typecheck gate. **Important**: `next.config.ts` calls `getCatalogSupabaseEnv()` at config-load time (`frontend/src/lib/supabase/env.ts:12-18`), which `throw`s if `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` are unset — CI's build step needs both present, but they're PUBLIC-by-design Supabase values (safe as dummy placeholders since build makes no network calls).
- `backend/tests/conftest.py`'s `db_pool` fixture reads `DB_URL` and `pytest.skip(...)` if unset — every DB-touching test in `integration/db/` and `integration/api/` (~15+ files) silently no-ops without a live Postgres.
- The existing `DB_URL` connects as the Postgres **superuser** role (local Supabase direct DB port 54322), which bypasses RLS entirely — this is exactly why no existing DB test exercises RLS.

**Gap 2 — RLS tests**: Confirmed from-scratch, not partial. Full inventory (all 5 migration files under `supabase/migrations/`):
- `products`, `product_variants`, `product_images`, `stock_movements`: RLS enabled, **zero** policies for `anon`/`authenticated`, **zero** GRANTs to them either — double-denied, not just RLS-denied.
- `service_role`: GRANTed full CRUD on `products/product_variants/product_images`; only `SELECT, INSERT` on `stock_movements` (append-only, also enforced by a trigger independent of RLS bypass — `BYPASSRLS` skips row security but not triggers, an untested interaction).
- 3 public views (`catalog_products`, `catalog_variants`, `catalog_product_images`, all `security_invoker = false`): `GRANT SELECT` to **both** `anon` and `authenticated` identically — there is no DB-level distinction between them; admin access is enforced entirely by the FastAPI JWT/JWKS layer, not Postgres roles.
- `variant_stock_levels`: internal only, no anon/authenticated grant.
- Soft-delete migration added `WHERE deleted_at IS NULL` filtering to all 3 catalog views — untested that `anon` actually stops seeing soft-deleted rows.
- `storage.objects`: one explicit policy, public SELECT for `anon` on the `product-photos` bucket only.
- Existing test coverage: **zero** RLS/role-scoped tests. The only role-boundary test, `backend/tests/architecture/test_frontend_service_role_boundary.py`, is a static grep of `frontend/src/*` for the literal string `SERVICE_ROLE` — proves the frontend never names the key, proves nothing about actual Postgres enforcement.

### Affected Areas
- `.github/workflows/*.yml` — new, doesn't exist.
- `backend/tests/integration/db/` — new RLS test module (e.g. `test_rls_policies.py`), reusing `db_pool`/`db_conn` conventions.
- `backend/tests/conftest.py` — `DB_URL` fixture semantics carry over unchanged; CI just needs to set the env var.
- `supabase/migrations/*.sql` — read-only reference for CI's migration-replay step; no changes needed.
- `frontend/next.config.ts` / `frontend/src/lib/supabase/env.ts` — CI build step needs dummy public env vars.

### Approaches

**Gap 1 (CI)**
1. **Bare/Supabase-flavored `postgres:` service container + migration replay** — fast, matches the app's actual `asyncpg`-only test surface. Open question whether a vanilla `postgres:17` image has `anon`/`authenticated`/`service_role` roles pre-created (likely needs bootstrap SQL). Effort: Medium.
2. **Full `supabase start` (Supabase CLI) in CI** — byte-identical to local dev, zero role-bootstrap guesswork. Pulls Studio/Auth/Storage/Realtime/Kong images CI never uses, slower/heavier. Effort: Medium.
3. **Lint/typecheck/unit-only CI, DB tests stay manual** — trivial, fast, but doesn't close the actual gap. Could be PR #1 of a chained sequence. Effort: Low but insufficient as end state.

**Gap 2 (RLS tests)**
1. **Direct `asyncpg` + `SET ROLE anon/service_role`** against Postgres — reuses all existing fixture infra, fastest to write. Doesn't exercise the PostgREST layer. Effort: Low-Medium.
2. **HTTP-level tests against local PostgREST** with real anon/service_role API keys — tests the actual client-facing code path. Requires the full Supabase stack, ties Gap 2 to CI Approach 2. Effort: Medium-High.
3. **Both, staged** — SQL-role tests now (Approach 1), PostgREST-level smoke tests explicitly deferred as a documented residual gap. Effort: Low-Medium overall.

### Recommendation

Bundle into **one** SDD change, named `ci-and-rls-tests` (no `admin-` prefix; this is infra/quality work, not admin-panel-scoped). Use CI Approach 1 (bare/Supabase-flavored Postgres service container, not full `supabase start`) + RLS Approach 3 (SQL-role-switch tests now, PostgREST-level tests deferred). If bundling risks the review budget, split via chained PRs within this one change (PR #1: CI skeleton + lint/typecheck/unit; PR #2: DB service container wiring existing DB tests in; PR #3: new RLS test module) rather than two separate SDD changes — RLS tests without CI repeats the exact "manual-only" pattern flagged as the gap in the first place.

### Risks
- **Secrets**: as scoped, no real Supabase project credentials appear necessary — CI DB tests need only an ephemeral local `DB_URL` (safe to hardcode, not a GitHub Secret), and `next build` needs only placeholder public env vars (anon key is public-by-design). Must be explicitly confirmed with the user — getting it wrong (real prod secrets in a public-visible workflow) is the top risk of a first CI pipeline.
- Role-bootstrap mechanism for `anon`/`authenticated`/`service_role` in a CI Postgres container is unconfirmed and must be resolved in design.
- First-ever GitHub Actions usage in this repo — conventions set now will likely be copied by future changes.
- A slow/flaky DB-backed CI gate risks becoming an ignored/red-always check — prioritize speed/reliability over broad coverage initially.
- Soft-delete view filtering and the service_role-vs-append-only-trigger interaction are good first RLS test cases beyond basic anon/service_role checks.

### Open Questions for Proposal
1. Postgres service container flavor/role-bootstrap mechanism — technical, design should decide.
2. Explicit no-real-secrets confirmation (safe local/placeholder values only).
3. RLS test scope for v1: SQL-role only (Approach 3, recommended) vs. also PostgREST smoke tests now.
4. Whether to add `ruff format --check` / frontend typecheck as new CI gates, or wire only the existing lint/test commands.

### Ready for Proposal
Yes.
