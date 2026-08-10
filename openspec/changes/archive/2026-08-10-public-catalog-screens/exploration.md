# Exploration: public-catalog-screens

Building the public-facing product catalog UI in the Next.js frontend, reading from the real Supabase schema archived in `supabase-schema`.

## Current State

- `frontend/src/app/` is unmodified `create-next-app` output: `page.tsx`, `layout.tsx`, `globals.css`, `favicon.ico`, `sw.ts`. No route groups exist — `(public)`/`(admin)` is only a *pinned contract* in `openspec/changes/archive/2026-08-09-initial-scaffolding/design.md` ("Admin URL contract pinned here: the `(admin)` route group serves under `/admin/*`; `(public)` serves catalog at `/` and `/catalog/*`"), not yet built.
- `frontend/package.json` has zero Supabase deps (`@supabase/supabase-js`, `@supabase/ssr` both absent). No `.env*` file anywhere references `SUPABASE`/`NEXT_PUBLIC_*` except `supabase/config.toml` itself.
- `frontend/src/lib/pwa/runtime-caching.ts` already encodes a full catalog-shaped Serwist matrix, written *before* any catalog page existed:
  - `/admin/*` or non-GET → `NetworkOnly` (must stay first)
  - `/`, `/catalog(/.*)?`, `/product/.*` (HTML/RSC nav) → `NetworkFirst`, 3s timeout, cache `catalog-pages`
  - `/api/catalog/*` (JSON) → `StaleWhileRevalidate`, cache `catalog-api` — implies the project already anticipated Next.js **Route Handlers** as a JSON layer for client-driven fetches (search/filter), not a FastAPI proxy
  - `*.supabase.co/storage/v1/object/public/*` → `CacheFirst` + `ExpirationPlugin` (120 entries/30d) + `CacheableResponsePlugin([0,200])`
  - Only `catalog-images` has an expiration ceiling; `catalog-pages`/`catalog-api` have none (acceptable since both attempt network first while online).
- `openspec/changes/archive/2026-08-09-supabase-schema/design.md` draws the intended data flow explicitly: `anon (Next.js (public)) --> PostgREST --> catalog_products / catalog_variants / catalog_product_images`, separately `service_role (FastAPI (admin)) --> PostgREST --> base tables`. **Direct Supabase reads from the public Next.js surface were already the pre-decided architecture.**
- RLS confirmed in `supabase/migrations/20260810000458_public_catalog_rls.sql`: all 4 base tables have RLS enabled with zero anon/authenticated policies; only `catalog_products`, `catalog_variants`, `catalog_product_images` are `GRANT SELECT`'d to `anon, authenticated` (`variant_stock_levels` is not). `catalog_variants.in_stock` is `COALESCE(SUM(quantity_delta),0) > 0` — boolean only.
- `product_images.variant_id` is nullable: `NULL` = product hero image, non-`NULL` = color-specific image — relevant to gallery/color-swap UI logic.
- Backend FastAPI `products` domain (`backend/src/gcell/products/**`) is in-memory only, missing `id`/`color`/`slug` alignment (confirmed unresolved deferred fast-follow), and unrelated to this catalog UI.
- `frontend/next.config.ts` only wires Serwist, no `images.remotePatterns`, no `cacheComponents`. Next.js 16 ships an opt-in "Cache Components" model (`cacheComponents: true` + `"use cache"`/`cacheLife`/`cacheTag`) replacing the previous `export const revalidate = N` ISR model — since the flag isn't set, this project defaults to the previous/classic model. Adopting Cache Components is a real, un-made decision for this change.
- `supabase/seed.sql` has ~2 products / 4 variants for local Docker only — confirms no environment beyond local Docker has ever had catalog data.

## Affected Areas

- `frontend/src/app/` — needs `(public)` route group (or flat `/` + `/catalog` + `/product/[slug]`), replacing the default page/layout
- `frontend/package.json` — add `@supabase/ssr` dependency
- `frontend/next.config.ts` — add `images.remotePatterns`, decide on `cacheComponents`
- `frontend/src/lib/pwa/runtime-caching.ts` — read-only reference; existing matrix already fits `/`, `/catalog/*`, `/product/*`, `/api/catalog/*`, Supabase Storage
- `frontend/src/lib/supabase/` (new) — server-only Supabase client factory, anon key only
- `frontend/.env.local` / `.env.example` (new) — `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `supabase/migrations/20260810000458_public_catalog_rls.sql`, `20260810000449_products_catalog.sql` — read-only reference for view/column contracts
- `backend/src/gcell/products/**` — confirmed NOT touched by this change

## Approaches — Data access layer

### 1. Direct Supabase reads from Next.js Server Components (`@supabase/ssr`, anon key, views only)
- Pros: matches the architecture already drawn in supabase-schema's design; zero new backend code; RLS+views are the already-verified security boundary; fewer moving parts and one fewer env-var surface; FastAPI stays free for future admin/write work.
- Cons: frontend now owns a Supabase-shaped dependency; if catalog business logic grows it eventually needs a real service layer somewhere.
- Effort: Low

### 2. Proxy through FastAPI `products` domain
- Pros: single backend surface for all data access, easier to bolt on cross-cutting concerns later.
- Cons: `products` domain is in-memory only today — this means wiring Supabase into the backend *first*, duplicating a read-only pass-through with no logic beyond `SELECT`, adding a network hop (browser->Next SSR->FastAPI->Postgres) and a second copy of Supabase credentials; contradicts the data-flow diagram already agreed in supabase-schema; makes the deferred Python domain alignment a hard prerequisite instead of a fast-follow.
- Effort: Medium-High

## Recommendation (data access)

Direct Supabase reads from Next.js Server Components via `@supabase/ssr`, hitting only `catalog_products` / `catalog_variants` / `catalog_product_images` with the anon key. This is not a new decision — it's the architecture already committed to in supabase-schema's data-flow diagram and verified end-to-end. Use `@supabase/ssr`'s `createServerClient` (not bare `@supabase/supabase-js`) even without auth today: it's Supabase's maintained App Router integration, avoiding a client-layer swap later when auth/cart lands. **Caveat**: `@supabase/ssr`'s exact cookie-adapter shape against Next 16's async `cookies()` postdates this agent's training — re-verify at install time.

## Approaches — Screen/route scope

### 1. Minimal
`/` (or `/catalog`) listing grid + `/product/[slug]` detail (variants: color, price, `in_stock`, images), static/ISR only, plain links between colors, no search/filter/pagination.
- Effort: Low

### 2. Medium (recommended)
Minimal + client-component color/variant picker on the detail page (swap image/price/in_stock on color select without full navigation). Search/filter/pagination still deferred.
- Effort: Medium

### 3. Full
Medium + text search/phone-model/color filters via an `/api/catalog/*` Route Handler (matches the pre-existing SWR matcher), pagination or infinite scroll, richer empty/error states.
- Effort: High

## Recommendation (scope)

Medium: listing + detail with an interactive color picker; defer search/filter/pagination to a follow-up once real catalog size is known — the seed catalog (~2 products) doesn't justify pagination yet, but a static-only picker would be a visibly worse UX than the effort it saves.

## Image Handling

- Derive `next.config.ts` -> `images.remotePatterns` from `NEXT_PUBLIC_SUPABASE_URL` at config-eval time (`new URL(process.env.NEXT_PUBLIC_SUPABASE_URL)`) rather than hardcoding — local Docker serves Storage from `127.0.0.1:54321` over `http`, hosted serves `https://<ref>.supabase.co`; hardcoding breaks one environment.
- Scope `pathname` to `/storage/v1/object/public/product-photos/**`, not a bare `/**` — matches the bucket-scoped storage policy.
- The existing Serwist Storage matcher checks `url.hostname.endsWith(".supabase.co")` only — it won't match local Docker's `127.0.0.1` storage URL. Dev-only gap, not a blocker; only staging/prod exercise the image-caching SW path.

## Risks

- Base-table leak via a coding mistake (querying `products`/`product_variants`/`product_images` instead of `catalog_*` views) — mitigated at the DB layer (RLS denies anon on base tables, verified), so a mistake yields empty/authorization error, not a leak; still enforce "views only" in review.
- Service-role key exposure — only `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` may ever be `NEXT_PUBLIC_*` in frontend; no service_role key belongs there.
- Two caching layers are mostly orthogonal (`NetworkFirst`/`SWR` both try network first online) but `catalog-pages`/`catalog-api` SW caches have no expiration ceiling, unlike `catalog-images` — an unbounded-offline-staleness gap worth a design note, not a correctness bug.
- `cacheComponents` is undecided — Next 16 defaults to the previous ISR model unless explicitly enabled; this change must pick one, since it determines how `in_stock`/`price` revalidation is expressed.
- No real (non-Docker) Supabase environment has ever had product data — first deploy needs an explicit empty-state UI plus a manual (Studio/SQL) plan to seed real products, since no admin panel exists yet.

## Ready for Proposal

Yes.
