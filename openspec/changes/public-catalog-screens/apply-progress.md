# Apply Progress: public-catalog-screens

## Batch 1 (this batch)

**Scope**: Phase 1 — Foundation (PR 1 of 3, `stacked-to-main` chain, branch `pr1-catalog-foundation` off `main`).
**Mode**: Strict TDD.
**Tasks**: 1.1–1.17, all complete.

### TDD Cycle Evidence

| Task | Unit | RED | GREEN | REFACTOR |
|---|---|---|---|---|
| 1.1/1.2 | `lib/catalog/columns.ts` | Failed: `columns` module not found | 6/6 tests pass | None needed |
| 1.4/1.5 | `lib/catalog/query-params.ts` | Failed: `query-params` module not found | 24/24 tests pass | None needed |
| 1.6/1.7 | `lib/catalog/derive.ts` | Failed: `derive` module not found | 8/8 tests pass | None needed |
| 1.8/1.9 | `lib/catalog/storage-url.ts` | Failed: `storage-url` module not found | 5/5 tests pass | None needed |
| 1.10/1.11 | `lib/supabase/image-pattern.ts` | Failed: `image-pattern` module not found | 5/5 tests pass | None needed |
| — (added, not in task list) | `lib/supabase/env.ts` | Failed: `env` module not found | 3/3 tests pass | None needed |

`lib/supabase/server.ts` (task 1.14) intentionally has no Vitest unit test: it requires Next's request-scoped `cookies()` async-local-storage context (`createRequestCatalogClient`) and `server-only`'s webpack-bundling guard, neither of which is meaningfully exercisable in a plain Vitest/jsdom run. This matches the task list itself — 1.12–1.16 carry no RED/GREEN marker, unlike 1.1–1.11. It is verified via `npm run build` (task 1.17) and will be exercised (and `vi.mock`'d) by the Phase 3 Route Handler tests per design.md's testing strategy.

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and result | `npm --prefix frontend test -- lib/catalog lib/supabase` → 8 test files, 58 tests, all passed |
| Runtime harness command/scenario and result | `npm --prefix frontend run build` → succeeded; log confirms `- Environments: .env.local` loads before `✓ Running next.config.ts`, and the relative `./src/lib/supabase/*` TS imports resolve under `next build --webpack` (both were open questions in design.md) |
| Rollback boundary | Delete `frontend/src/lib/catalog/`, `frontend/src/lib/supabase/`; revert `frontend/next.config.ts`, `frontend/package.json`, `frontend/package-lock.json`, `frontend/.gitignore`; delete `frontend/.env.example` |

### Key facts verified during apply

- `@supabase/ssr@0.12.4` installed. Its non-deprecated `CookieMethodsServer` type (`node_modules/@supabase/ssr/dist/module/types.d.ts`) confirms the `getAll` (required) / `setAll` (optional) adapter shape assumed by design.md — not the deprecated `get`/`set`/`remove` trio. `server.ts` implements accordingly.
- `@supabase/supabase-js@2.112.2` was pulled in automatically as `@supabase/ssr`'s peer dependency (npm auto-install); not added explicitly to `package.json` since design.md's File Changes table only lists `@supabase/ssr` and `server-only`. Build's TypeScript pass succeeded, confirming resolution works.
- Migration `20260810000458_public_catalog_rls.sql` read directly to confirm exact view columns — `columns.ts` constants match verbatim: `catalog_products(id,slug,name,description,created_at)`, `catalog_variants(id,product_id,phone_model,color,price,in_stock)`, `catalog_product_images(id,product_id,variant_id,storage_path,alt_text,sort_order)`.
- `frontend/.gitignore`'s blanket `.env*` was silently swallowing `frontend/.env.example` (confirmed via `git check-ignore -v` before/after) — added `!.env.example` so it stays committed while `.env.local` stays ignored. Root `.gitignore`'s existing `!.env.example` did not cover this because the more specific `frontend/.gitignore` pattern took precedence for paths under `frontend/`.
- `next.config.ts` build log shows `- Environments: .env.local` printed before `✓ Running next.config.ts`, confirming Next 16 loads `.env.local` before config evaluation — resolves a design.md open question.
- `.env.local` (gitignored) uses the Supabase CLI's well-known default local demo anon JWT (same for every local project unless `supabase/config.toml` overrides the JWT secret; `config.toml` here has no such override) — not a project secret.
- Local Docker/Supabase was not running during this batch; not required — no live Supabase read exists in Phase 1 (pure functions + config only), and `npm run build` succeeds without it.

### Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `frontend/src/lib/catalog/columns.ts` | Created | `CATALOG_RELATIONS` allowlist + 3 exported column-list constants |
| `frontend/src/lib/catalog/columns.test.ts` | Created | Exact-column-match + forbidden-token (cost/quantity) tests |
| `frontend/src/lib/catalog/types.ts` | Created | `CatalogProductRow`/`CatalogVariantRow`/`CatalogImageRow`, no behavior |
| `frontend/src/lib/catalog/query-params.ts` | Created | `sanitizeSearchTerm`, `parsePageParam`, `parseLimitParam` |
| `frontend/src/lib/catalog/query-params.test.ts` | Created | Per-metacharacter-class strip tests, truncation, page/limit boundaries |
| `frontend/src/lib/catalog/derive.ts` | Created | `derivePriceFrom`, `deriveHeroImage`, `deriveListingCard` |
| `frontend/src/lib/catalog/derive.test.ts` | Created | Price-from equal/differing, hero-image 3-branch fallback chain |
| `frontend/src/lib/catalog/storage-url.ts` | Created | `toPublicPhotoUrl` (bucket-relative path → public Storage URL) |
| `frontend/src/lib/catalog/storage-url.test.ts` | Created | Local + hosted URL construction, slash-duplication edge cases |
| `frontend/src/lib/supabase/env.ts` | Created | `getCatalogSupabaseEnv` — validates the two `NEXT_PUBLIC_*` vars |
| `frontend/src/lib/supabase/env.test.ts` | Created | Present/missing-var cases (not an explicit task, added under Strict TDD) |
| `frontend/src/lib/supabase/server.ts` | Created | `createAnonCatalogClient` (sync) + `createRequestCatalogClient` (async) |
| `frontend/src/lib/supabase/image-pattern.ts` | Created | `buildProductPhotoPattern`, zero-import pure builder |
| `frontend/src/lib/supabase/image-pattern.test.ts` | Created | Local/hosted pattern shape, pinned `search: ""`, malformed-URL throw |
| `frontend/next.config.ts` | Modified | `images.remotePatterns` wired via `buildProductPhotoPattern(env url)` |
| `frontend/package.json` | Modified | `+ @supabase/ssr`, `+ server-only` |
| `frontend/package-lock.json` | Modified | Lockfile update for the two new dependencies (generated) |
| `frontend/.gitignore` | Modified | Added `!.env.example` exception |
| `frontend/.env.example` | Created | Two `NEXT_PUBLIC_*` vars, no service_role key |
| `frontend/.env.local` | Created (gitignored, not committed) | Local dev values using Supabase CLI's default demo anon key |

### Review-budget note

`tasks.md`'s forecast estimated slice 1 at ~320–400 lines. Actual authored diff (excluding the generated `package-lock.json`) is ~855 lines — driven by exhaustive per-case RED tests the design explicitly mandates (one test per PostgREST metacharacter class, one per hero-image fallback branch, one per page/limit boundary value) plus one additional tested unit (`lib/supabase/env.ts`) beyond the literal task list, added because Strict TDD Mode is active project-wide and the unit is pure/testable. No scope beyond Phase 1's 17 tasks was implemented. Flagging for the orchestrator/user in case PR1 itself should be reviewed as more than one PR — no further action taken here since the user's instructions explicitly scoped this batch to exactly Phase 1.

### Deviations from Design

None — implementation matches design.md precisely, including the exact `images.remotePatterns` explicit-object form, the two-factory Supabase client split, and the column allowlist read directly from the migration.

### Issues Found

None.

### Remaining Tasks

- [ ] Phase 2 (PR 2): Pages & UI — not in scope for this batch, not started.
- [ ] Phase 3 (PR 3): Search API — not in scope for this batch, not started.
- [ ] Phase 4: Cross-Cutting Verification — depends on Phase 2/3.

### Status

17/17 Phase 1 tasks complete. Ready for `sdd-verify` on the PR1 slice, or for PR2 to branch from `pr1-catalog-foundation` once this PR merges to `main`.
