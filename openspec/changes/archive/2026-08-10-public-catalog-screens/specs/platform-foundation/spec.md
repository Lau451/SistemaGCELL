# Delta for platform-foundation

## MODIFIED Requirements

### Requirement: PWA Runtime-Caching Strategy Decision
The Serwist PWA configuration MUST document a concrete runtime-caching strategy for public catalog routes, and every real catalog route created by the application MUST conform to that documented strategy's matcher patterns in `frontend/src/lib/pwa/runtime-caching.ts`.
(Previously: allowed the strategy to be documented in advance with no real catalog route required to exist yet.)

#### Scenario: Strategy remains documented
- GIVEN the Serwist configuration files
- WHEN the caching strategy for public catalog routes/images is inspected
- THEN a named strategy per asset class (NetworkFirst for pages, StaleWhileRevalidate for API, CacheFirst for storage images) MUST be documented in `runtime-caching.ts`

#### Scenario: Real catalog routes conform to the pinned matcher
- GIVEN the `public-catalog-ui` and `catalog-search-api` capabilities have introduced real routes (`/`, `/catalog`, `/product/*`, `/api/catalog/*`)
- WHEN each route's path is tested against the corresponding matcher in `runtime-caching.ts`
- THEN every route MUST match its intended matcher
- AND `runtime-caching.ts` itself MUST remain unmodified by the change that introduced those routes
