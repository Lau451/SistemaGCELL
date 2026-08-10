# public-catalog-ui Specification

## Purpose

Public-facing storefront: browse and search the catalog, view product detail, and pick a color/variant without a full navigation. Reads only `catalog_*` Supabase views, under classic ISR (`revalidate = 300`).

## Requirements

### Requirement: Catalog Listing Renders Products
The `/` and `/catalog` routes MUST render a listing sourced from `catalog_products`, showing at minimum image, name, and price per product, and MUST honor search term, phone-model filter, color filter, and pagination parameters.

#### Scenario: Default listing
- GIVEN the catalog has published products
- WHEN a visitor requests `/` or `/catalog` with no query parameters
- THEN the first page of products MUST render with image, name, and price

#### Scenario: Search and filter narrow results
- GIVEN products of multiple phone models and colors exist
- WHEN a visitor supplies a search term and/or a model/color filter
- THEN only matching products SHALL render, sourced from `/api/catalog/*`

#### Scenario: Pagination advances the result set
- GIVEN more products exist than fit on one page
- WHEN a visitor requests the next page
- THEN a distinct, non-overlapping set of products MUST render

### Requirement: Product Detail Page With Interactive Color Picker
`/product/[slug]` MUST render a product's variants and MUST let a visitor switch the selected color/variant client-side, updating image, price, and `in_stock` without a full page navigation.

#### Scenario: Detail loads default variant
- GIVEN a product with multiple color variants exists at its slug
- WHEN a visitor requests `/product/[slug]`
- THEN the page MUST render the product with an initial variant's image, price, and stock state

#### Scenario: Selecting a color swaps state without navigation
- GIVEN the detail page is rendered with variant A selected
- WHEN the visitor selects variant B's color swatch
- THEN the displayed image, price, and `in_stock` MUST update to variant B's values
- AND no full-page navigation/reload SHALL occur

### Requirement: Out-of-Stock Variants Stay Visible and Selectable
Variants where `in_stock` is false MUST remain visible on the detail page and MUST stay clickable/selectable; they MUST NOT be hidden and MUST NOT be rendered as a disabled (non-interactive) control. Selecting an out-of-stock variant MUST still swap the displayed image and price, per the color/variant picker requirement, and MUST show a "Sin stock" badge/indicator.

#### Scenario: Out-of-stock color swatch is shown selectable with a badge
- GIVEN a product has one variant with `in_stock = false`
- WHEN the detail page renders
- THEN that variant's swatch MUST be visible and clickable
- AND it MUST display a "Sin stock" badge/indicator
- AND selecting it MUST update the displayed image and price like any other variant

### Requirement: Multi-Price Products Show a "From" Price
When a product's variants have differing prices, the listing MUST display the minimum variant price prefixed with "from" rather than a single misleading price.

#### Scenario: Variants share one price
- GIVEN all of a product's variants share the same price
- WHEN it renders on the listing
- THEN that single price MUST render without a "from" prefix

#### Scenario: Variants have different prices
- GIVEN a product's variants have at least two distinct prices
- WHEN it renders on the listing
- THEN the price MUST render as "from {min variant price}"

### Requirement: Deliberate Empty and No-Results States
The listing MUST render an explicit empty-catalog message when zero products exist, and a distinct no-results message when a search/filter yields zero matches; neither case MAY render a blank or broken page.

#### Scenario: Catalog has zero products
- GIVEN no products exist in `catalog_products`
- WHEN a visitor requests the listing
- THEN a deliberate "no products yet" empty state MUST render, not a blank page

#### Scenario: Search/filter matches nothing
- GIVEN products exist but none match the supplied search term or filters
- WHEN a visitor applies that search/filter
- THEN a distinct "no results" state MUST render, not the empty-catalog state and not a blank page

### Requirement: ISR Freshness Window
Listing and detail pages MUST be statically generated with `revalidate = 300` seconds, so price and stock data are never more stale than 5 minutes under normal traffic.

#### Scenario: Page is served from cache within the window
- GIVEN a listing or detail page was generated less than 300 seconds ago
- WHEN a visitor requests it again
- THEN the cached render MAY be served without hitting Supabase

#### Scenario: Page regenerates after the window
- GIVEN a listing or detail page was generated more than 300 seconds ago
- WHEN a visitor requests it
- THEN Next.js MUST trigger regeneration so subsequent requests reflect current data

### Requirement: Sensitive Inventory Fields Never Reach Rendered Output
No page under `(public)` MUST ever render an exact stock quantity or a `cost` value, in visible text, HTML attributes, or embedded JSON (e.g. RSC payload/`__NEXT_DATA__`).

#### Scenario: Rendered HTML is inspected for sensitive fields
- GIVEN any listing or detail page render
- WHEN the full HTML response, including embedded script/JSON payloads, is inspected
- THEN no numeric stock quantity or `cost` field/value MUST be present anywhere in it

### Requirement: Catalog Routes Conform to the Pinned Runtime-Caching Matcher
Every route this capability introduces (`/`, `/catalog`, `/catalog/*`, `/product/*`) MUST match the existing catalog-page matcher pattern in `frontend/src/lib/pwa/runtime-caching.ts`; that file MUST NOT be modified to accommodate a route shape.

#### Scenario: Route paths match the pinned pattern
- GIVEN the final set of implemented page routes
- WHEN each route's path is tested against `CATALOG_PAGE_PATTERN` in `runtime-caching.ts`
- THEN every route MUST match, and `runtime-caching.ts` MUST be byte-identical to its pre-change state
