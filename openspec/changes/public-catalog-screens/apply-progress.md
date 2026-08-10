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

## Batch 2 (this batch)

**Scope**: Phase 2 — Pages & UI (PR 2 of 3, `stacked-to-main` chain, branch `pr2-catalog-ui` off `main`, per the orchestrator-resolved chain strategy recorded in Engram `sdd/public-catalog-screens/tasks`).
**Mode**: Strict TDD.
**Tasks**: 2.1–2.21, all complete.

### TDD Cycle Evidence

| Task | Unit | RED | GREEN | REFACTOR |
|---|---|---|---|---|
| 2.3–2.6 | `lib/catalog/queries.ts` | Failed: `./queries` module not found | 15/15 tests pass (incl. source-grep column-safety test) | None needed |
| 2.7/2.8 | `components/catalog/catalog-empty-state.tsx` | Failed: `./catalog-empty-state` module not found | 4/4 tests pass | None needed |
| 2.9/2.10 | `components/catalog/product-card.tsx` | Failed: `./product-card` module not found | 5/5 tests pass | None needed |
| 2.11 (added, not itemized in task list) | `components/catalog/catalog-listing-view.tsx` | Failed: `./catalog-listing-view` module not found | 4/4 tests pass | None needed |
| 2.12/2.13 | `components/catalog/variant-picker.tsx` | Failed: `./variant-picker` module not found | 6/6 tests pass (incl. `fetch`-never-called and out-of-stock-not-disabled assertions) | None needed |
| 2.19/2.20 | `app/(public)/*` route-segment config + `runtime-caching.ts` conformance | Written and run against the already-created pages/config (see "Deviations" — pages were implemented in a single pass, not test-first) | 4/4 + 4/4 tests pass | Extracted `CatalogListingPageContent` out of `page.tsx` into `catalog-listing-content.tsx` after `next build`'s route-export validator rejected the extra named export — see Issues Found |

`app/(public)/layout.tsx`, `page.tsx`, `catalog/page.tsx`, `product/[slug]/page.tsx`, `product/[slug]/not-found.tsx` (tasks 2.1, 2.2, 2.14–2.18) are Server Components with no dedicated RTL test — per design.md's testing strategy they stay markup-logic-free and are verified via the 2.19 revalidate-export test, the 2.20 conformance test, `next build`'s static-generation pass, and a manual dev-server smoke test (see Work Unit Evidence). This mirrors Phase 1's precedent for `lib/supabase/server.ts`.

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and result | `npm --prefix frontend test -- "src/app/(public)" src/components/catalog src/lib/catalog/queries.test.ts src/lib/pwa/__tests__/catalog-route-conformance.test.ts` → all passing (also verified via full-suite run below) |
| Full-suite result | `npm --prefix frontend test` → 15 test files, 100 tests, all passed (was 8 files/58 tests after PR1) |
| Runtime harness command/scenario and result | `npm --prefix frontend run build` → succeeded; `/` and `/catalog` prerendered **static** with `revalidate: 5m`, confirming `createAnonCatalogClient()` genuinely avoids opting the route into dynamic rendering; `/product/[slug]` is `ƒ` (on-demand, no `generateStaticParams`), matching design.md exactly. Build succeeded with **no live Supabase reachable** (Docker daemon not running in this sandbox — see Issues Found) because `listCatalogProducts` returned `{ok:false}` and the pages statically rendered the `error` empty-state variant instead of throwing, empirically confirming the "reads never throw" design decision. |
| Manual dev-server smoke (partial substitute for `supabase start`) | `npm --prefix frontend run dev`, then `curl` against `/`, `/catalog`, `/product/fundas-iphone-15`, `/product/does-not-exist` → all `200`; `/product/does-not-exist` renders the `not-found.tsx` UI (`data-testid="product-not-found"`, text "No encontramos este producto"); `/` and `/product/fundas-iphone-15` render the `error` empty-state (no live Supabase — see Issues Found). No exceptions in the dev server log after a clean restart. |
| Rollback boundary | Delete `frontend/src/app/(public)/`, `frontend/src/components/catalog/`, `frontend/src/lib/catalog/queries.ts` + `queries.test.ts`, `frontend/src/lib/pwa/__tests__/catalog-route-conformance.test.ts`; restore `frontend/src/app/page.tsx` from git history; revert `frontend/src/app/layout.tsx` metadata and the `server-only` alias in `frontend/vitest.config.mts` |

### Key facts verified during apply

- Read `node_modules/next/dist/docs/01-app/` (per `frontend/AGENTS.md`'s mandatory pre-read for this pinned Next 16.3.0) for `page.js`/`layout.js`/`route-groups`/`dynamic-routes`/`not-found` conventions before writing any route file. Two concrete corrections came from this: `priority` on `next/image` is deprecated in Next 16 in favor of `preload` (used `preload` in `variant-picker.tsx`); and `next build`'s TypeScript pass validates that a `page.tsx` module exports **only** the fixed allowed set (`default`, `revalidate`, `metadata`, ...) — an extra named export (`CatalogListingPageContent`) fails the build even though Vitest/`tsc --noEmit` alone don't catch it.
- `server-only`'s default package-export condition (`index.js`) throws unconditionally on any import; it only resolves to the safe no-op `empty.js` via the `"react-server"` package-export condition, which Vitest's plain Node module resolution does not apply. This blocked task 2.19 (`import` each `page.tsx` to check `revalidate`) until a scoped `resolve.alias` for `server-only` → `node_modules/server-only/empty.js` was added to `frontend/vitest.config.mts`. Confirmed this alias does not affect React's own module resolution (full pre-existing suite re-ran green after adding it).
- `queries.ts`'s query shapes deviate from design.md's literal table in two places, both driven by the user's explicit instruction that **every** `.select()` in `queries.ts` use one of the three exported column constants (`CATALOG_PRODUCT_COLUMNS`/`CATALOG_VARIANT_COLUMNS`/`CATALOG_IMAGE_COLUMNS`) and never a bespoke string literal: the scope-by-model/color query selects the full `CATALOG_VARIANT_COLUMNS` row and extracts `product_id` in memory (design showed `select("product_id")`), and `getCatalogFilterOptions` does the same for `phone_model`/`color` (design showed `select("phone_model,color")`). Enforced by a RED source-grep test (`queries.test.ts`) asserting every `.select(` argument in `queries.ts` is one of the three constants, plus a second grep asserting no literal-string `.from(` call exists outside the typed `catalogFrom()` helper.
- `next build`'s static-generation succeeded for `/` and `/catalog` with **no Supabase reachable** (Docker Desktop's daemon was not running in this sandbox, contrary to the task description's stated assumption — confirmed via `docker ps`/`curl 127.0.0.1:54321` both failing). Inspected the generated `.next/server/app/index.html`/`catalog.html` directly and confirmed they contain `catalog-empty-state-error`, proving the build fell back to the designed `error` state rather than failing — this is the strongest available evidence for design.md's "a build-time outage bakes an error state, not a build failure" decision, short of a real Supabase connection.
- A manual dev-server smoke test hit a transient Next dev-mode `Jest worker encountered 2 child process exceptions` 500 on `/product/does-not-exist`; traced it to an earlier Bash-tool command timeout that killed the dev server's child process pool mid-request, not an application bug. A clean `taskkill`-and-restart reproduced all four routes (`/`, `/catalog`, `/product/fundas-iphone-15`, `/product/does-not-exist`) returning `200` with correct content and no further errors in the dev log.

### Files Changed

| File | Action | What Was Done |
|------|--------|---------------|
| `frontend/src/app/page.tsx` | Deleted | Scaffold `create-next-app` page; collided with `(public)/page.tsx` at `/` |
| `frontend/src/app/layout.tsx` | Modified | Replaced scaffold `title`/`description` metadata with real copy |
| `frontend/vitest.config.mts` | Modified | Added a scoped `resolve.alias` for `server-only` → its own `empty.js`, so `page.tsx` modules (which transitively import `server-only` via `lib/supabase/server.ts`) can be statically imported under Vitest |
| `frontend/src/lib/catalog/queries.ts` | Created | 6 query builders: `scopeProductIdsByVariant`, `listCatalogProducts`, `listVariantsForProducts`, `listImagesForProducts`, `getCatalogProductBySlug`, `getCatalogFilterOptions`; single `catalogFrom()` `.from()` call site; `CatalogQueryResult<T>` never-throws result type |
| `frontend/src/lib/catalog/queries.test.ts` | Created | Hand-rolled recording fake Supabase client; per-builder relation/column/chain-composition assertions; source-grep column-safety + no-literal-`.from()` tests |
| `frontend/src/components/catalog/catalog-empty-state.tsx` | Created | `empty-catalog`/`no-results`/`error` variants, distinct `role="status"` + `data-testid` |
| `frontend/src/components/catalog/catalog-empty-state.test.tsx` | Created | Distinct testid/content per variant; `no-results`/`error` action links present |
| `frontend/src/components/catalog/product-card.tsx` | Created | Image (with `ImageOff` placeholder fallback), name, "Desde {min}" vs single price |
| `frontend/src/components/catalog/product-card.test.tsx` | Created | Price-prefix, link href, name, placeholder-on-null-image tests |
| `frontend/src/components/catalog/catalog-listing-view.tsx` | Created | Pure grid composing `ProductCard`s + `CatalogEmptyState` |
| `frontend/src/components/catalog/catalog-listing-view.test.tsx` | Created | Grid-vs-empty-state selection tests (added under Strict TDD; not separately itemized in tasks.md) |
| `frontend/src/components/catalog/variant-picker.tsx` | Created | `"use client"` color/variant picker; local-state-only swap; out-of-stock swatches clickable with "Sin stock" badge, never `disabled` |
| `frontend/src/components/catalog/variant-picker.test.tsx` | Created | Default-selection, out-of-stock-not-disabled, swap-updates-price/badge, `fetch`-never-called tests |
| `frontend/src/app/(public)/layout.tsx` | Created | Public shell (header/nav) |
| `frontend/src/app/(public)/catalog-listing-content.tsx` | Created | Shared fetch+derive logic for `/` and `/catalog` (extracted out of `page.tsx` — see Issues Found) |
| `frontend/src/app/(public)/page.tsx` | Created | `/` listing, `revalidate = 300` |
| `frontend/src/app/(public)/catalog/page.tsx` | Created | `/catalog` alias, `metadata.alternates.canonical = "/"` |
| `frontend/src/app/(public)/product/[slug]/page.tsx` | Created | Detail page, `revalidate = 300`, `await params`, `maybeSingle` → `notFound()` |
| `frontend/src/app/(public)/product/[slug]/not-found.tsx` | Created | Unknown-slug UI |
| `frontend/src/app/(public)/revalidate.test.ts` | Created | Imports each `page.tsx`/`catalog/page.tsx`/`product/[slug]/page.tsx`, asserts `revalidate === 300` and the canonical metadata |
| `frontend/src/lib/pwa/__tests__/catalog-route-conformance.test.ts` | Created | Pinned-sha256 byte-identity check on `runtime-caching.ts` + matcher assertions for `/`, `/catalog`, `/product/x` |

### Review-budget note

Actual authored diff for this batch is **21 files changed, 1541 insertions(+), 71 deletions(-)** (`git diff --stat`), well above `tasks.md`'s slice-2 forecast of ~300–380 lines — the same overshoot pattern flagged in PR1's apply-progress, driven by exhaustive per-unit RED tests (query-builder chain composition per builder, all three empty-state variants, both price-display branches, the full out-of-stock interaction matrix) that Strict TDD Mode and design.md's testing strategy both mandate. No scope beyond Phase 2's 21 tasks was implemented; the one addition beyond the literal task list (`catalog-listing-view.test.tsx`) follows PR1's established precedent of testing every pure/presentational unit under Strict TDD even when a task wasn't individually itemized for it. Flagging for the orchestrator/user in case this PR's size should be reconsidered — no further action taken here since delivery was already resolved to `stacked-to-main` with PR2 = Phase 2 as its own slice.

### Deviations from Design

- **`queries.ts` scope/filter-options query shapes**: design.md's literal query-shapes table shows `select("product_id")` and `select("phone_model,color")` as bespoke string literals for `scopeProductIdsByVariant`/`getCatalogFilterOptions`. Per the user's explicit instruction (every `.select()` must use one of the three exported column constants, enforced by a RED grep test), both now select the full `CATALOG_VARIANT_COLUMNS` row and derive the needed field(s) in memory. Functionally equivalent, structurally stricter — documented above under "Key facts verified during apply".
- **Shared listing content lives in `catalog-listing-content.tsx`, not exported from `page.tsx`**: design.md's data-flow diagram implies `/catalog` reuses `/`'s logic but doesn't specify the file boundary. `next build`'s TypeScript pass rejects a `page.tsx` module with any named export beyond the fixed allowed set, so the shared `CatalogListingPageContent` async function was extracted into its own non-route module that both `page.tsx` files import. `frontend/next.config.ts`/File Changes table in design.md didn't anticipate this constraint; noting it here as a design gap discovered during apply, not a deviation from stated intent.
- Everything else (route file layout, hero-image fallback usage, "Desde {min}" pricing, out-of-stock-selectable variant picker, empty/no-results/error state split, `revalidate = 300`, byte-identical `runtime-caching.ts`) matches design.md precisely.

### Issues Found

- `next build`'s route-export validator rejected the initial `(public)/page.tsx` (which exported both `default` and `CatalogListingPageContent`) with `TS2344: ... does not satisfy the constraint '{ [x: string]: never; }'`. Fixed by extracting the shared function into `catalog-listing-content.tsx` — see Deviations. This was invisible to `vitest`/`tsc --noEmit` alone; only caught by the actual `next build` runtime harness, confirming the value of running it rather than relying on unit tests in isolation.
- Local Supabase (Docker) was **not** actually running in this execution sandbox, despite the task description's stated assumption. `docker ps` showed no containers and the Docker Desktop daemon was unreachable (`npipe` connection error); `curl http://127.0.0.1:54321` failed to connect. Manual verification was therefore done against the graceful `error`-state fallback path instead of real seed data — see "Key facts verified during apply" for what this did and did not prove. The full component/query-builder test suite (100/100 passing) is the primary correctness evidence for this batch; a real `supabase start` + browse pass against the 2-product/4-variant seed (confirming the hero-image fallback and multi-price "Desde" display against real data) is still recommended before this PR is considered fully manually verified.
- One transient dev-server 500 (Jest worker crash) traced to the Bash tool's own command-timeout killing a child process mid-request — not a code defect. See "Key facts verified during apply".

### Remaining Tasks

- [ ] Phase 3 (PR 3): Search API — not in scope for this batch, not started.
- [ ] Phase 4: Cross-Cutting Verification — depends on Phase 3.

### Status

38/38 Phase 1+2 tasks complete (17/17 Phase 1, 21/21 Phase 2). Ready for `sdd-verify` on the PR2 slice, or for PR3 to branch from `pr2-catalog-ui` once this PR merges.
