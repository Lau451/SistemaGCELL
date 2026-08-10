# Tasks: Public Catalog Screens

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~950-1050 (slice1 ~320-400, slice2 ~380-450, slice3 ~250-300) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 foundation -> PR2 pages/UI -> PR3 search API |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending (user decision required) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Pure catalog domain + Supabase client factories + image-pattern config | PR 1 | `npm --prefix frontend test -- lib/catalog lib/supabase` | `npm --prefix frontend run build` (config eval) | Delete `lib/catalog/`, `lib/supabase/`, revert `next.config.ts`/`package.json` |
| 2 | Listing + detail pages, variant picker, empty/no-results states, scaffold removal | PR 2 | `npm --prefix frontend test -- app/(public) components/catalog` | `supabase start` + `npm --prefix frontend run dev`, browse `/`, `/product/fundas-iphone-15` | Delete `app/(public)/`, restore `app/page.tsx` |
| 3 | `/api/catalog` Route Handler + client-side filters wiring | PR 3 | `npm --prefix frontend test -- app/api/catalog components/catalog/catalog-filters` | `supabase start` + dev server, hit `GET /api/catalog?q=...` | Delete `app/api/catalog/`, `catalog-filters.tsx`; revert wiring |

## Phase 1: Foundation (PR 1) — pure domain, Supabase clients, config

- [ ] 1.1 RED `lib/catalog/columns.test.ts`: column constants match view columns; no `cost`/`quantity` token.
- [ ] 1.2 GREEN `lib/catalog/columns.ts`: `CATALOG_RELATIONS` allowlist + 3 column constants.
- [ ] 1.3 Create `lib/catalog/types.ts`: row types matching views exactly (no test, no behavior).
- [ ] 1.4 RED `lib/catalog/query-params.test.ts`: `sanitizeSearchTerm` strips each PostgREST metachar class; `q` >80 chars truncated; `page`/`limit` boundary cases (0, -1, "abc", 999).
- [ ] 1.5 GREEN `lib/catalog/query-params.ts`.
- [ ] 1.6 RED `lib/catalog/derive.test.ts`: price-from (equal vs differing prices); hero-image fallback chain (null-variant image -> default variant's first image -> placeholder).
- [ ] 1.7 GREEN `lib/catalog/derive.ts`.
- [ ] 1.8 RED `lib/catalog/storage-url.test.ts`: `storage_path` -> public URL, local + hosted.
- [ ] 1.9 GREEN `lib/catalog/storage-url.ts`.
- [ ] 1.10 RED `lib/supabase/image-pattern.test.ts`: `buildProductPhotoPattern` for `http://127.0.0.1:54321` and `https://<ref>.supabase.co`; `search` pinned `""`.
- [ ] 1.11 GREEN `lib/supabase/image-pattern.ts`.
- [ ] 1.12 Install `@supabase/ssr` + `server-only`; read installed package's cookie-adapter shape (`getAll`/`setAll` vs `get`/`set`/`remove`) before 1.14.
- [ ] 1.13 Create `lib/supabase/env.ts`: validate `NEXT_PUBLIC_SUPABASE_URL`/`_ANON_KEY`.
- [ ] 1.14 Create `lib/supabase/server.ts`: `createAnonCatalogClient` (sync, no `cookies()`) + `createRequestCatalogClient` (async, awaits `cookies()`), adapter shape per 1.12.
- [ ] 1.15 Modify `next.config.ts`: `images.remotePatterns` via `buildProductPhotoPattern(env url)`.
- [ ] 1.16 Create `.env.example`: two `NEXT_PUBLIC_*` vars only; confirm `.env.local` stays gitignored.
- [ ] 1.17 Verify: `npm --prefix frontend test` (new suite green) + `npm --prefix frontend run build`.

## Phase 2: Pages & UI (PR 2)

- [ ] 2.1 Delete `frontend/src/app/page.tsx` (scaffold; collides with `(public)/page.tsx` at `/`).
- [ ] 2.2 Modify `frontend/src/app/layout.tsx`: replace scaffold metadata.
- [ ] 2.3 Create `lib/catalog/queries.ts`: 6 builders (scope, listing, variants-for, images-for, detail, filter-options) against `catalog_*` views, column constants only.
- [ ] 2.4 RED `lib/catalog/queries.test.ts`: fake chainable client — relation names in allowlist, exact column strings, `.in`/`.or`/`.range` composition.
- [ ] 2.5 RED source-grep test: every `.select(` in `queries.ts` uses only exported column constants (catches future `select("*")`).
- [ ] 2.6 GREEN: adjust `queries.ts` until 2.4/2.5 pass.
- [ ] 2.7 Create `components/catalog/catalog-empty-state.tsx`: `empty-catalog` / `no-results` / `error` variants, distinct `role="status"` + `data-testid`.
- [ ] 2.8 RED RTL test: three states render distinct content/testid (spec empty/no-results scenarios).
- [ ] 2.9 Create `components/catalog/product-card.tsx`: single price vs "desde {min}" display.
- [ ] 2.10 RED RTL test: same-price vs differing-price rendering.
- [ ] 2.11 Create `components/catalog/catalog-listing-view.tsx`: pure grid composing cards + empty state.
- [ ] 2.12 Create `components/catalog/variant-picker.tsx` (`"use client"`): swatch click swaps image/price/`in_stock`; out-of-stock swatch stays clickable, shows "Sin stock" badge (not `disabled`).
- [ ] 2.13 RED RTL + user-event test: swatch click swaps state; `vi.spyOn(globalThis,"fetch")` never called after mount; out-of-stock swatch clickable with badge.
- [ ] 2.14 Create `app/(public)/layout.tsx`: public shell.
- [ ] 2.15 Create `app/(public)/page.tsx`: listing, `revalidate = 300`, fetch + props only.
- [ ] 2.16 Create `app/(public)/catalog/page.tsx`: alias, `metadata.alternates.canonical = "/"`.
- [ ] 2.17 Create `app/(public)/product/[slug]/page.tsx`: detail, `revalidate = 300`, `await params`, `maybeSingle` -> `notFound()`.
- [ ] 2.18 Create `app/(public)/product/[slug]/not-found.tsx`.
- [ ] 2.19 Test: import each `page.tsx` module, assert `revalidate === 300` (no jsdom render).
- [ ] 2.20 RED conformance test: import unmodified `runtime-caching.ts`, invoke matcher for `/`, `/catalog`, `/product/x`; assert match + file byte-identical to pre-change.
- [ ] 2.21 Verify: `npm --prefix frontend test`; manual browse against local Supabase seed (`supabase start`, 2 products/~4 variants).

## Phase 3: Search API (PR 3)

- [ ] 3.1 Create `app/api/catalog/route.ts`: `GET` handler, `createRequestCatalogClient`, builders from 2.3, params via `query-params.ts`.
- [ ] 3.2 RED handler tests (import `GET` + `NextRequest`): no-params -> first page; combined `q`+`model`+`color`+`page` narrows result; zero matches -> well-formed empty result.
- [ ] 3.3 RED threat-matrix tests: each PostgREST metachar class stripped; `q` >80 truncated; `page=0/-1/abc`, `limit=999` -> `400 invalid_query`; unknown `model`/`color` -> `200` no-results; upstream failure -> `503 catalog_unavailable`.
- [ ] 3.4 RED response test: no `cost`/quantity key in any successful response, including empty results.
- [ ] 3.5 GREEN: implement `route.ts` until 3.2-3.4 pass; set `Cache-Control` per design.
- [ ] 3.6 RED conformance test: `/api/catalog` path matches `isCatalogApiRead` in unmodified `runtime-caching.ts`.
- [ ] 3.7 Create `components/catalog/catalog-filters.tsx` (`"use client"`): search/model/color/pagination controls, calls `/api/catalog`, `history.replaceState`.
- [ ] 3.8 RED RTL test: filter change fetches `/api/catalog`, replaces cards, no navigation.
- [ ] 3.9 Wire filters + client listing into `(public)/page.tsx` / `catalog/page.tsx` composition.
- [ ] 3.10 Verify: `npm --prefix frontend test`; `npm --prefix frontend run build`; manual smoke against local Supabase.

## Phase 4: Cross-Cutting Verification

- [ ] 4.1 Sensitive-field check: render listing + detail, inspect full HTML incl. RSC/`__NEXT_DATA__` payload for `cost`/quantity (spec requirement, all 3 slices).
- [ ] 4.2 Confirm `frontend/src/lib/pwa/runtime-caching.ts` is byte-identical to pre-change across all slices.
- [ ] 4.3 Full-suite `npm --prefix frontend test` + `npm --prefix frontend run build` after PR 3 merges.
