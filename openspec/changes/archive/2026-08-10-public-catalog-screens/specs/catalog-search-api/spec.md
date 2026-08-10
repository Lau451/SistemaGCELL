# catalog-search-api Specification

## Purpose

`/api/catalog/*` Route Handler contract: serves search, filter, and pagination queries against `catalog_*` views for the public listing, using the same server-only anon Supabase client as the pages.

## Requirements

### Requirement: Search, Filter, and Pagination Query Contract
`/api/catalog/*` MUST accept a search term, an optional phone-model filter, an optional color filter, and pagination parameters, and MUST return only products matching all supplied criteria.

#### Scenario: No parameters returns first page
- GIVEN the endpoint is called with no query parameters
- WHEN the request is processed
- THEN the first page of all catalog products MUST be returned

#### Scenario: Combined search + filters + page narrow the result
- GIVEN a search term, a model filter, a color filter, and a page number are all supplied
- WHEN the request is processed
- THEN only products satisfying every supplied criterion, for the requested page, MUST be returned

#### Scenario: Zero matches returns an empty, well-formed result
- GIVEN criteria that match no product
- WHEN the request is processed
- THEN the response MUST be a successful, well-formed empty result set, not an error

### Requirement: View-Only Data Source
Every query issued by `/api/catalog/*` MUST read from the `catalog_products`, `catalog_variants`, or `catalog_product_images` views only, and MUST NOT reference any base table.

#### Scenario: Queried relations are inspected
- GIVEN the Route Handler's implementation
- WHEN the relation names it queries are inspected
- THEN every one MUST be a `catalog_*` view name, and none MUST be a base table name

### Requirement: Server-Only Anon-Key Client Boundary
`/api/catalog/*` MUST use the shared server-only Supabase client built from `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and MUST NOT construct or use a client authenticated with a service_role key.

#### Scenario: Handler uses the shared anon client
- GIVEN the Route Handler's implementation
- WHEN its Supabase client construction is inspected
- THEN it MUST reuse the server-only factory in `frontend/src/lib/supabase/`
- AND no service_role key or credential MUST appear in its code or environment

### Requirement: Sensitive Fields Excluded From Every Response
No `/api/catalog/*` JSON response MUST ever include an exact stock quantity or a `cost` value, for any query shape or result size.

#### Scenario: Response body is inspected
- GIVEN any successful `/api/catalog/*` response, including empty results
- WHEN its JSON body is inspected
- THEN no numeric stock quantity or `cost` field MUST be present anywhere in it

### Requirement: API Routes Conform to the Pinned Runtime-Caching Matcher
`/api/catalog/*` MUST match the existing `isCatalogApiRead` matcher in `frontend/src/lib/pwa/runtime-caching.ts` (`StaleWhileRevalidate`), and that file MUST NOT be modified.

#### Scenario: API route path matches the pinned matcher
- GIVEN the implemented `/api/catalog/*` route
- WHEN its path is tested against `isCatalogApiRead`
- THEN it MUST match, and `runtime-caching.ts` MUST be byte-identical to its pre-change state
