# Proposal: Public Catalog Screens

## Intent

The catalog data contract is live (`catalog_*` views, RLS, photo bucket — archived `supabase-schema`) but nothing reads it. `frontend/src/app/` is still unmodified `create-next-app` output, so the business has zero customer-facing surface. This change builds the public catalog: browse, search, and pick a product's color.

## Product Decisions (user-confirmed)

- **Scope: Full** — listing + detail with interactive color picker, *plus* text search, phone-model/color filters, and pagination. Chosen over the exploration's "Medium" recommendation: real catalog growth is expected soon, and retrofitting search into a finished listing costs more than building it now.
- **Caching: classic ISR** (`export const revalidate = N`), **not** Next 16 Cache Components (`cacheComponents: true` + `"use cache"`) — lower risk on a brand-new feature with thin precedent.
- **Data access: direct Supabase reads from Server Components** via `@supabase/ssr`, anon key, `catalog_*` views only. Carried forward from the archived `supabase-schema` data-flow diagram — confirmed, not re-litigated.

## Scope

### In Scope

- `(public)` route group: listing at `/` (+ `/catalog`) with search, filters, pagination; `/product/[slug]` detail with a client color/variant picker swapping image + price + `in_stock` without navigation.
- `/api/catalog/*` Route Handler serving the client-driven search/filter/pagination queries.
- `frontend/src/lib/supabase/` server-only client factory; `@supabase/ssr` dependency.
- `next.config.ts` → `images.remotePatterns` derived from `NEXT_PUBLIC_SUPABASE_URL` at config-eval time, `pathname` scoped to `/storage/v1/object/public/product-photos/**`.
- `.env.local` + `.env.example` with `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` only; verify `.gitignore` already covers `.env.local`.
- Explicit empty-catalog, no-results, and error states — never a blank or broken page.
- Vitest/RTL tests for new components, pages, and the Route Handler.

### Out of Scope

- Backend FastAPI `products` domain (stays in-memory), admin panel, cart/checkout/auth.
- `cacheComponents` adoption; Playwright (still deferred project-wide).
- Seeding a real deployed Supabase environment — manual/out-of-band via Studio or SQL until an admin panel exists.
- `frontend/src/lib/pwa/runtime-caching.ts` edits — routes must fit the existing matcher, not the reverse.

## Capabilities

### New Capabilities

- `public-catalog-ui`: listing, detail, variant/color picker, image rendering, empty/no-results/error states, ISR freshness expectations.
- `catalog-search-api`: `/api/catalog/*` contract — search term, model/color filters, pagination, view-only data source, anon-key boundary.

### Modified Capabilities

- `platform-foundation`: "PWA Runtime-Caching Strategy Decision" currently allows *no real catalog route to exist*. Real routes now exist, so the requirement becomes: created routes MUST fall inside the pinned matcher patterns.

## Approach

Server Components read `catalog_products` for the listing and `catalog_products` + `catalog_variants` + `catalog_product_images` for detail, statically rendered with `export const revalidate = N`. Search/filter/pagination run client-side against the Route Handler, which reuses the same server-only anon client and the same views. `product_images.variant_id IS NULL` = hero image, non-null = color image, driving the picker swap. Route shapes stay inside the pinned URL contract (`/`, `/catalog`, `/product/*`, `/api/catalog/*`) so the Serwist matrix (`NetworkFirst` pages, `StaleWhileRevalidate` API, `CacheFirst` storage images) applies untouched.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `frontend/src/app/(public)/**` | New | Listing, detail, layout, states |
| `frontend/src/app/api/catalog/**` | New | Search/filter/pagination handler |
| `frontend/src/lib/supabase/**` | New | Server-only anon client factory |
| `frontend/next.config.ts` | Modified | `images.remotePatterns` |
| `frontend/package.json` | Modified | `@supabase/ssr` |
| `frontend/.env.example` | New | Two `NEXT_PUBLIC_*` vars |
| `frontend/src/lib/pwa/runtime-caching.ts` | Unchanged | Read-only conformance check |
| `backend/**` | Unchanged | Deliberate |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Code names a base table instead of a `catalog_*` view | Med | RLS already denies anon (empty result, not a leak); enforce "views only" in review + a test asserting queried relation names |
| A service-role key reaches frontend env | Low | Only two `NEXT_PUBLIC_*` vars permitted; `.env.example` is the allowlist |
| Empty catalog on first real deploy | High | Empty-state UI is an in-scope success criterion; seeding is an accepted manual step |
| `@supabase/ssr` vs Next 16 async `cookies()` drift | Med | Re-verify against official docs at install time before pinning (project convention) |
| Route group changes URL shape and misses the Serwist matcher | Low | Assert final URLs against the existing matcher patterns before apply completes |
| Unbounded offline staleness (`catalog-pages`/`catalog-api` have no `ExpirationPlugin`) | Low | Note only; `NetworkFirst`/`SWR` self-correct online — defer to a PWA-tuning change |
| Exceeds 400-line review budget | High | Stack slices: (1) client + env + config, (2) listing + detail + picker, (3) Route Handler + search/filter/pagination |

## Rollback Plan

Nothing is deployed and no user data is created. Revert the frontend commits: deleting the `(public)` route group, `api/catalog/`, `lib/supabase/`, the `next.config.ts` `images` block, and the `@supabase/ssr` dependency returns `frontend/` to scaffold state. Database, migrations, storage, and backend are untouched, so there is no data or backend rollback.

## Dependencies

- Local Supabase running (`supabase start`) with `seed.sql` applied, for development and tests.
- Archived `supabase-schema` views, RLS grants, and `product-photos` bucket (already merged).
- `@supabase/ssr` version re-verified against Next.js 16 at install time.

## Success Criteria

- [ ] Listing renders seeded products with hero image and price; `/product/[slug]` renders all variants.
- [ ] Selecting a color updates image, price, and `in_stock` without a full navigation.
- [ ] Search, model/color filters, and pagination work through `/api/catalog/*` and return only view-sourced data.
- [ ] An empty catalog renders a deliberate empty state; a zero-result search renders a distinct no-results state.
- [ ] No exact stock quantity or `cost` value is reachable anywhere in the rendered output or API responses.
- [ ] Frontend env contains only `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`; `.env.local` is untracked.
- [ ] Images load in both local Docker (`127.0.0.1:54321`) and a hosted `*.supabase.co` project without a config edit.
- [ ] All created routes match the existing `runtime-caching.ts` patterns with that file unmodified.
- [ ] Pinned Vitest suite passes, including new component, page, and Route Handler tests.

## Proposal question round

Scope, caching model, and data access were confirmed directly by the user. These product questions remain open; current working assumptions are stated so `sdd-spec` is not blocked, but the user may correct any of them:

1. **Landing route** — is `/` the catalog listing itself, or a marketing page linking to `/catalog`? *Assumption: `/` IS the listing; `/catalog` is an alias/equivalent.*
2. **Freshness tolerance** — how stale may price and `in_stock` be for a buyer? *Assumption: `revalidate = 300` (5 min); `sdd-design` may adjust.*
3. **Listing price display** when a product's variants differ in price — single price, "from X", or a range? *Assumption: "from {min}".*
4. **Out-of-stock behaviour** — hide out-of-stock variants, or show them disabled? *Assumption: show, visibly disabled — availability is a real buying signal.*
5. **Filter source** — are phone-model filter options derived from existing catalog rows, or a fixed curated list? *Assumption: derived from catalog data, so it can never offer an empty filter.*
