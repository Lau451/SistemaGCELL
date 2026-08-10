# Design: Public Catalog Screens

## Technical Approach

Three thin layers, each independently testable:

1. **Access layer** (`src/lib/supabase/`) — one `@supabase/ssr` module exporting two factories over shared internals: a prerender-safe anonymous client for ISR pages, and a request-bound client for Route Handlers.
2. **Catalog domain** (`src/lib/catalog/`) — column allowlists, row types, a relation allowlist, query builders, param parsing, and pure derivations. Every function is pure or takes an injected client, so it is unit-testable with no Next.js runtime.
3. **UI** (`src/app/(public)/`, `src/components/catalog/`) — `page.tsx` files are thin async shells (fetch + `revalidate` + pass props). All markup lives in non-async presentational components that RTL can render in jsdom.

Route shapes are fixed by the untouched `src/lib/pwa/runtime-caching.ts` matchers, verified below against the real source.

## Architecture Decisions

### Decision: Two client factories, not one

**Choice**: `createAnonCatalogClient()` (sync, cookie adapter returns `[]`, no `cookies()` call) for ISR pages; `createRequestCatalogClient()` (async, awaits `cookies()`) for Route Handlers.
**Alternatives**: single async factory everywhere; bare `@supabase/supabase-js`.
**Rationale**: `cookies()` is a Request-time API — calling it in a page opts the route into dynamic rendering and **silently kills `revalidate = 300`**. A single async factory would therefore contradict the proposal's classic-ISR decision. Bare `supabase-js` would force a client-layer swap when auth lands. Two named exports over one internal builder keeps ISR intact and keeps the auth-ready path.

### Decision: `@supabase/ssr` cookie adapter shape — VERIFY AT INSTALL

**Choice**:

```ts
import "server-only";
import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";

export async function createRequestCatalogClient() {
  const store = await cookies();                 // Next 16: async
  return createServerClient(url, anonKey, {
    cookies: {
      getAll: () => store.getAll(),              // adapter stays SYNC
      setAll: () => {},                          // no auth yet; RSC cannot set
    },
  });
}
```

**Key insight**: `@supabase/ssr` never calls `cookies()` itself. You `await` it first and hand the library a **synchronous** adapter over the resolved store — so Next 16's async `cookies()` never leaks into the adapter contract. Async-`cookies()` compatibility is therefore structural, not version-dependent.
**Unverified**: that the installed `@supabase/ssr` version exposes `getAll`/`setAll` (v0.5+ shape) rather than the deprecated `get`/`set`/`remove` trio. This postdates reliable knowledge. **`sdd-apply` MUST read the installed package's own README/types before writing this file** and correct the adapter keys if they differ. The two-factory split confines any correction to one module.

### Decision: Separate queries + in-memory join, no PostgREST embedding

**Choice**: 2–4 flat `.select()` calls per page; join by `product_id` in TypeScript.
**Alternatives**: PostgREST resource embedding (`catalog_products(...,catalog_variants(...))`).
**Rationale**: embedding across **views** depends on PostgREST inferring relationships from underlying base-table FKs — version-sensitive and untestable with a stubbed client. Flat queries make the column allowlist provable and the fake-client test trivial.

### Decision: No `generateStaticParams`; reads never throw

**Choice**: omit `generateStaticParams`; every catalog read returns `{ ok: true, data } | { ok: false, reason }`.
**Alternatives**: prerender all slugs at build.
**Rationale**: `generateStaticParams` would make `next build` require a reachable Supabase (local Docker is not available in CI/Vercel builds). On-demand ISR + `dynamicParams` (default `true`) renders new products on first request. The result type means a build-time outage bakes an error state, not a build failure — and it makes empty/no-results/error first-class UI states rather than exception paths.

### Decision: `model` and `color` are filters; `q` searches name/description only

**Choice**: `q` → `.or("name.ilike…,description.ilike…")` on `catalog_products`; `model`/`color` → exact-match scope query on `catalog_variants` → `.in("id", productIds)`.
**Alternatives**: search also matching `phone_model`.
**Rationale**: `catalog_products` does **not** expose `model` (confirmed in `20260810000458_public_catalog_rls.sql`); only `catalog_variants.phone_model` does. Matching model inside `q` would need a union pass over two scoping queries. The model dropdown already covers that intent at zero extra cost.

### Decision: UI copy in Spanish, code in English

**Choice**: user-facing strings es-AR; identifiers/comments/artifacts English. Prices via `Intl.NumberFormat("es-AR", { style: "currency", currency: "ARS" })`.
**Rationale**: seeded catalog data is Spanish (`fundas-iphone-15`, colors `negro`/`transparente`).

## Route Structure — Verified Against `runtime-caching.ts`

`CATALOG_PAGE_PATTERN = /^\/(catalog(\/.*)?|product\/.*)?$/`; `CATALOG_API_PREFIX = "/api/catalog"`.

| File | URL | Matcher entry | Handler |
|---|---|---|---|
| `(public)/page.tsx` | `/` | optional group empty → match | `NetworkFirst` `catalog-pages` |
| `(public)/catalog/page.tsx` | `/catalog` | `catalog(\/.*)?` → match | `NetworkFirst` |
| `(public)/product/[slug]/page.tsx` | `/product/{slug}` | `product\/.*` → match | `NetworkFirst` |
| `app/api/catalog/route.ts` | `/api/catalog` | `startsWith("/api/catalog")` | `StaleWhileRevalidate` `catalog-api` |

**Hard constraint discovered**: `src/app/page.tsx` (scaffold) and `(public)/page.tsx` both resolve to `/` → build-time route conflict. The scaffold page MUST be **deleted**, not left in place.

`/catalog` renders the same `CatalogListingView` as `/` (query params preserved) and sets `metadata.alternates.canonical = "/"`. A `redirect()` was rejected: it would drop `?q=`/`?model=` on deep links.

**Note (no change required)**: `isSupabaseStoragePublicObject` requires `url.hostname.endsWith(".supabase.co")`, so local `127.0.0.1:54321` images are simply not service-worker cached in development. Hosted behaviour is unaffected.

## Data Flow

```
Browser ──GET /──▶ (public)/page.tsx  [revalidate=300, static]
                      │
                      ├─ createAnonCatalogClient()   (no cookies() → stays static)
                      ├─ getCatalogFilterOptions()   catalog_variants → distinct model/color
                      ├─ scopeProductIds(model,color) catalog_variants → product_id[]
                      ├─ listCatalogProducts(q,ids,page) catalog_products (+count exact)
                      ├─ listVariantsFor(ids)        catalog_variants
                      └─ listImagesFor(ids)          catalog_product_images
                             │
                             ▼  deriveListingCard() (pure)
                      <CatalogListingView cards filters state />

Filter/search change ──GET /api/catalog?q&model&color&page&limit──▶ route.ts
                      └─ createRequestCatalogClient() → same 4 builders → JSON
                             │ (SW StaleWhileRevalidate)
                             ▼
                      <CatalogListingClient /> replaces cards + URL (history.replaceState)

/product/[slug] ──▶ getProductBySlug(slug) ─ maybeSingle → notFound()
                 ├─ listVariantsFor([id])  ┐ all variants + all images
                 └─ listImagesFor([id])    ┘ serialized once into
                             ▼
                      <VariantPicker "use client" />  ← local state only, zero fetch
```

## Query Shapes

Column allowlists (`src/lib/catalog/columns.ts`), exactly the view columns:

```ts
export const CATALOG_RELATIONS = ["catalog_products", "catalog_variants", "catalog_product_images"] as const;
export type CatalogRelation = (typeof CATALOG_RELATIONS)[number];

export const CATALOG_PRODUCT_COLUMNS = "id,slug,name,description,created_at" as const;
export const CATALOG_VARIANT_COLUMNS = "id,product_id,phone_model,color,price,in_stock" as const;
export const CATALOG_IMAGE_COLUMNS = "id,product_id,variant_id,storage_path,alt_text,sort_order" as const;
```

| Query | Shape |
|---|---|
| Scope (only if `model`/`color` set) | `.from("catalog_variants").select("product_id").eq("phone_model", m).eq("color", c)` → unique `product_id[]` |
| Listing | `.from("catalog_products").select(CATALOG_PRODUCT_COLUMNS, { count: "exact" })` + `.in("id", ids)?` + `.or(\`name.ilike."%q%",description.ilike."%q%"\`)?` + `.order("created_at", { ascending: false })` + `.range(off, off + limit - 1)` |
| Variants for page | `.from("catalog_variants").select(CATALOG_VARIANT_COLUMNS).in("product_id", ids).order("color")` |
| Images for page | `.from("catalog_product_images").select(CATALOG_IMAGE_COLUMNS).in("product_id", ids).order("sort_order")` |
| Detail | `.from("catalog_products").select(CATALOG_PRODUCT_COLUMNS).eq("slug", slug).maybeSingle()` then the two above with `[product.id]` |
| Filter options | `.from("catalog_variants").select("phone_model,color")` → dedupe + sort in memory |

**Hero-image fallback (from seed inspection)**: `seed.sql` inserts **no** `variant_id IS NULL` rows. Resolution order: first image with `variant_id === null` by `sort_order` → else the default variant's first image → else a local placeholder. A design that assumed a hero row always exists would render a blank listing against the real seed.

**Public image URL**: `storage_path` is bucket-relative (`fundas-iphone-15/negro.jpg`), so `${NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/public/product-photos/${storage_path}`.

## Route Handler Contract — `GET /api/catalog`

| Param | Type | Default | Validation |
|---|---|---|---|
| `q` | string | — | trim, ≤80 chars, `sanitizeSearchTerm()` strips `, . ( ) " \ * %` |
| `model` | string | — | exact match, ≤80 chars |
| `color` | string | — | exact match, ≤80 chars |
| `page` | int | `1` | `≥ 1`, else `400` |
| `limit` | int | `12` | `1..48`, else `400` |

```ts
type CatalogListResponse = {
  items: CatalogCard[];   // id, slug, name, priceFrom, hasPriceRange, inStock, colors, heroImageUrl, heroImageAlt
  page: number; limit: number; total: number; totalPages: number;
  filters: { models: string[]; colors: string[] };
  applied: { q: string | null; model: string | null; color: string | null };
};
```

`400 { error: "invalid_query", details }` on bad params; `503 { error: "catalog_unavailable" }` on upstream failure (Workbox `StaleWhileRevalidate` only caches `200`, so a `503` cannot poison `catalog-api`). Success sets `Cache-Control: public, max-age=0, s-maxage=300, stale-while-revalidate=600`.

## Variant / Color Picker

`src/components/catalog/variant-picker.tsx`, `"use client"`. Props: `variants: CatalogVariant[]`, `imagesByVariantId: Record<string, CatalogImage[]>`, `heroImages: CatalogImage[]`. State: `selectedVariantId` (init: first `in_stock`, else first). Selection swaps image, price, and stock badge from **already-serialized props — zero additional fetch**.

Efficiency confirmed: a realistic product has 1–8 colors × 1–5 images ≈ ≤40 rows of ~6 short fields — a few KB of RSC payload, strictly cheaper than one round-trip per swatch. The initially selected image gets `priority`; the rest lazy-load and are then served by the `catalog-images` `CacheFirst` cache on hosted.

Swatches render as `role="radiogroup"` with `role="radio"` buttons (Base UI `RadioGroup` if a primitive is vendored). Out-of-stock swatches are **visually marked and keep an "Sin stock" badge**; see Open Questions.

## `next.config.ts` — `images.remotePatterns`

Pure builder in `src/lib/supabase/image-pattern.ts` (zero imports, so `next.config.ts` can import it relatively and Vitest can test it directly):

```ts
export const PRODUCT_PHOTO_PATHNAME = "/storage/v1/object/public/product-photos/**";

export function buildProductPhotoPattern(rawSupabaseUrl: string) {
  const url = new URL(rawSupabaseUrl);                 // throws early on a malformed env value
  return {
    protocol: url.protocol.replace(":", "") as "http" | "https",
    hostname: url.hostname,
    port: url.port,          // "54321" locally, "" for https://<ref>.supabase.co
    pathname: PRODUCT_PHOTO_PATHNAME,
    search: "",
  };
}
```

`http://127.0.0.1:54321` → `{protocol:"http", hostname:"127.0.0.1", port:"54321", …}`; `https://abc.supabase.co` → `{protocol:"https", hostname:"abc.supabase.co", port:"", …}`. Same code, no edit between environments. The explicit object form is chosen over Next 16's `new URL(...)` shorthand because it pins `search: ""` (omitting `search` implies `**`, per `next/dist/docs/.../image.md`). **Verify at apply**: that `.env.local` is loaded before `next.config.ts` evaluation, and that a relative TS import from the config resolves under `--webpack`.

## Empty / No-Results / Error States

Single component `catalog-empty-state.tsx` with a `variant` prop; the listing picks the variant from data, never from a thrown error:

| Variant | Condition | Content | Filter UI |
|---|---|---|---|
| `empty-catalog` | `ok && total === 0 && !hasActiveQuery` | "Estamos preparando el catálogo" | hidden |
| `no-results` | `ok && total === 0 && hasActiveQuery` | "No encontramos productos para …" + **Limpiar filtros** | visible, values retained |
| `error` | `!ok` | "No pudimos cargar el catálogo" + Reintentar | hidden |

Each variant renders a distinct `role="status"` heading + `data-testid`, so RTL asserts they are genuinely different states.

## Structural Guarantee: `cost` / exact stock unreachable

Four layers, cheapest first:

1. `catalog_*` views simply do not contain `cost` or `quantity_on_hand` — anon has no GRANT on base tables or `variant_stock_levels`.
2. `catalogFrom(client, relation: CatalogRelation)` is the **only** `.from()` call site; naming `product_variants` is a compile error.
3. Every `.select()` passes one of the three exported column constants — **no `select("*")` exists anywhere**.
4. RED test `columns.test.ts`: asserts each constant's token set equals the exact view column list from the migration, and that the concatenation of all three constants contains none of `cost`, `quantity`, `quantity_on_hand`, `stock_movements`. A second test greps `src/lib/catalog/queries.ts` source for `select(` and asserts every argument is one of the constants (catches a future `select("*")`).

## File Changes

| File | Action | Description |
|---|---|---|
| `frontend/src/app/page.tsx` | **Delete** | Conflicts with `(public)/page.tsx` at `/` |
| `frontend/src/app/layout.tsx` | Modify | Replace scaffold metadata title/description |
| `frontend/src/app/(public)/layout.tsx` | Create | Public shell (header/nav) |
| `frontend/src/app/(public)/page.tsx` | Create | `/` listing, `revalidate = 300` |
| `frontend/src/app/(public)/catalog/page.tsx` | Create | `/catalog` alias, canonical `/` |
| `frontend/src/app/(public)/product/[slug]/page.tsx` | Create | Detail, `revalidate = 300`, `await params` |
| `frontend/src/app/(public)/product/[slug]/not-found.tsx` | Create | Unknown slug state |
| `frontend/src/app/api/catalog/route.ts` | Create | `GET` search/filter/pagination |
| `frontend/src/lib/supabase/env.ts` | Create | Reads + validates the two `NEXT_PUBLIC_*` vars |
| `frontend/src/lib/supabase/server.ts` | Create | Two factories, `server-only` |
| `frontend/src/lib/supabase/image-pattern.ts` | Create | Pure `remotePatterns` builder |
| `frontend/src/lib/catalog/columns.ts` | Create | Relation + column allowlists |
| `frontend/src/lib/catalog/types.ts` | Create | Row types matching views exactly |
| `frontend/src/lib/catalog/queries.ts` | Create | The six builders above |
| `frontend/src/lib/catalog/query-params.ts` | Create | Parse/validate/sanitize `q,model,color,page,limit` |
| `frontend/src/lib/catalog/derive.ts` | Create | `deriveListingCard`, hero fallback, price-from |
| `frontend/src/lib/catalog/storage-url.ts` | Create | `storage_path` → public URL |
| `frontend/src/components/catalog/catalog-listing-view.tsx` | Create | Pure grid (jsdom-testable) |
| `frontend/src/components/catalog/product-card.tsx` | Create | Card, "desde {min}" |
| `frontend/src/components/catalog/catalog-filters.tsx` | Create | `"use client"` search/model/color/pagination |
| `frontend/src/components/catalog/catalog-empty-state.tsx` | Create | Three variants |
| `frontend/src/components/catalog/variant-picker.tsx` | Create | `"use client"` color picker |
| `frontend/next.config.ts` | Modify | `images.remotePatterns` from builder |
| `frontend/package.json` | Modify | `+ @supabase/ssr`, `+ server-only` |
| `frontend/.env.example` | Create | Two `NEXT_PUBLIC_*` vars only |

~14 new source files + tests. Nothing in `backend/`, `supabase/`, or `src/lib/pwa/`.

## Testing Strategy

| Layer | What to test | Approach |
|---|---|---|
| Pure unit | `buildProductPhotoPattern`, `parseCatalogQuery`, `sanitizeSearchTerm`, `deriveListingCard` (price-from, hero fallback), `toPublicPhotoUrl` | Plain Vitest, zero mocks — highest value per line |
| Query builders | relation names ∈ allowlist, exact column strings, `.in/.or/.range` composition | Hand-rolled chainable fake client recording every call; assert the recorded calls |
| Column safety | no `cost`/quantity token; no `select("*")` in `queries.ts` source | Constant assertions + source regex (RED first) |
| Server Components | *not rendered in jsdom* | All markup extracted into non-async presentational components rendered with RTL; `page.tsx` holds only fetch + `export const revalidate`, asserted by importing the module and checking `revalidate === 300` |
| Client picker | swatch click swaps image/price/stock badge; **`fetch` never called** | RTL + `user-event`, `vi.spyOn(globalThis, "fetch")` asserted `not.toHaveBeenCalled()` |
| Route Handler | status codes, JSON shape, param validation, no sensitive keys in the payload | Import `GET` directly, call with `new NextRequest("http://localhost/api/catalog?…")`, `vi.mock("@/lib/supabase/server")` |
| Conformance | every created URL matches the intended `catalogRuntimeCaching` entry | New test importing the **unmodified** `runtime-caching.ts` and invoking `catalogRuntimeCaching[n].matcher({ url, request })` for `/`, `/catalog`, `/product/x`, `/api/catalog` |
| E2E | — | Unavailable (Playwright deferred project-wide per `openspec/config.yaml`) |

Runner unchanged: `npm --prefix frontend test`.

## Threat Matrix

The reference matrix targets shell/VCS/process boundaries; this change has none. All rows explicit `N/A`.

| Boundary | Applicability |
|---|---|
| Documentation-like paths | N/A — no file classification or execution |
| Git repository selection | N/A — no VCS automation |
| Commit state | N/A — no commit automation |
| Push state | N/A — no push automation |
| PR commands | N/A — no PR automation |

**Supplementary (the boundary that does apply): untrusted HTTP query input.**

| Case | Safe behaviour | RED test |
|---|---|---|
| `q` with PostgREST operators (`,` `.` `(` `)` `"` `*` `%`) | `sanitizeSearchTerm` strips them before `.or()`; no filter-syntax injection | one test per metacharacter class |
| `q` longer than 80 chars | truncated, `200` | boundary test |
| `page=0`, `page=-1`, `page=abc`, `limit=999` | `400 invalid_query`, no query issued | one test per value |
| `model`/`color` unknown value | `200` with `no-results`, never `500` | one test |
| Upstream Supabase failure | `503 catalog_unavailable`, uncacheable by the SW | one test |

## Migration / Rollout

No data migration. Deleting `src/app/page.tsx` is the only destructive step and is covered by the proposal's revert-the-commits rollback. Requires a running local Supabase for dev/tests; a build with an unreachable Supabase succeeds and renders the `error` state rather than failing.

## Review-Budget Slicing (recommendation for `sdd-tasks`)

The proposal's 3 slices are **confirmed with one refinement** — move the pure catalog domain into slice 1 so slice 2 is UI-only:

| # | Slice | Contents | Est. lines |
|---|---|---|---|
| 1 | Foundation | `lib/supabase/*`, `lib/catalog/{columns,types,query-params,derive,storage-url}.ts`, `next.config.ts`, `.env.example`, `package.json`, + their pure tests | ~250–320 |
| 2 | Pages & picker | `(public)/**`, delete scaffold `page.tsx`, `lib/catalog/queries.ts`, presentational components, `variant-picker.tsx`, conformance test | ~300–380 |
| 3 | Search API | `api/catalog/route.ts`, `catalog-filters.tsx`, client wiring, handler tests | ~200–260 |

Each slice ships something verifiable on its own: slice 1 is green unit tests + a passing build, slice 2 is a browsable catalog, slice 3 adds interactive search. `sdd-tasks` owns the authoritative forecast.

## Open Questions

- [ ] **Out-of-stock swatch interactivity.** The proposal recorded "visible but disabled". A literally `disabled` swatch makes that colour's image and price unreachable, which works against "availability is a real buying signal". This design keeps the swatch **selectable** and marks it "Sin stock" (the future purchase CTA is what gets disabled). Confirm with the user, or `sdd-spec` pins the literal reading.
- [ ] `@supabase/ssr` cookie-adapter key names (`getAll`/`setAll` vs `get`/`set`/`remove`) MUST be read from the installed package at apply time.
- [ ] Whether Next 16 loads `.env.local` before evaluating `next.config.ts`, and whether a relative TS import from the config resolves under `next build --webpack`.
