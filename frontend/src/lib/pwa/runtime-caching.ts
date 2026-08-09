import {
  CacheFirst,
  CacheableResponsePlugin,
  ExpirationPlugin,
  NetworkFirst,
  NetworkOnly,
  StaleWhileRevalidate,
  type RouteMatchCallbackOptions,
  type RuntimeCaching,
} from "serwist";

/**
 * Catalog runtime-caching matrix (order-sensitive).
 *
 * This array is meant to be prepended to Serwist's `defaultCache`
 * (`@serwist/next/worker`), which already handles `_next/static`,
 * `_next/image`, and fonts correctly.
 *
 * Matcher order matters: entries are evaluated top-to-bottom and the first
 * match wins, so `/admin/*` and non-GET requests MUST stay first or a later,
 * broader matcher could capture them.
 *
 * @see design.md "Decision: Serwist runtime-caching matrix" for the full
 * rationale per asset class.
 */

const ADMIN_PATH_PREFIX = "/admin";
const CATALOG_API_PREFIX = "/api/catalog";
const SUPABASE_STORAGE_PUBLIC_SEGMENT = "/storage/v1/object/public/";

// `/`, `/catalog`, `/catalog/*`, `/product/*` — catalog HTML/RSC navigations.
const CATALOG_PAGE_PATTERN = /^\/(catalog(\/.*)?|product\/.*)?$/;

const CATALOG_NETWORK_TIMEOUT_SECONDS = 3;
const CATALOG_IMAGE_MAX_ENTRIES = 120;
const ONE_DAY_IN_SECONDS = 24 * 60 * 60;
const CATALOG_IMAGE_MAX_AGE_SECONDS = 30 * ONE_DAY_IN_SECONDS;
const CATALOG_IMAGE_CACHEABLE_STATUSES = [0, 200];

type Matcher = (options: RouteMatchCallbackOptions) => boolean;

const isAdminOrMutatingRequest: Matcher = ({ url, request }) =>
  url.pathname === ADMIN_PATH_PREFIX ||
  url.pathname.startsWith(`${ADMIN_PATH_PREFIX}/`) ||
  request.method !== "GET";

const isCatalogPageNavigation: Matcher = ({ url, request }) =>
  request.method === "GET" && CATALOG_PAGE_PATTERN.test(url.pathname);

const isCatalogApiRead: Matcher = ({ url, request }) =>
  request.method === "GET" && url.pathname.startsWith(CATALOG_API_PREFIX);

const isSupabaseStoragePublicObject: Matcher = ({ url, request }) =>
  request.method === "GET" &&
  url.hostname.endsWith(".supabase.co") &&
  url.pathname.includes(SUPABASE_STORAGE_PUBLIC_SEGMENT);

export const catalogRuntimeCaching: RuntimeCaching[] = [
  // 1. `/admin/*` or any non-GET request: never land in a shared cache.
  //    Must stay first, or a broader matcher below would capture it.
  {
    matcher: isAdminOrMutatingRequest,
    handler: new NetworkOnly(),
  },
  // 2. Catalog navigations: price/stock correctness beats instant paint
  //    while online; falls back to the cache when offline or slow.
  {
    matcher: isCatalogPageNavigation,
    handler: new NetworkFirst({
      cacheName: "catalog-pages",
      networkTimeoutSeconds: CATALOG_NETWORK_TIMEOUT_SECONDS,
    }),
  },
  // 3. `/api/catalog/*` JSON reads: instant render, background refresh.
  {
    matcher: isCatalogApiRead,
    handler: new StaleWhileRevalidate({
      cacheName: "catalog-api",
    }),
  },
  // 4. Supabase Storage public product images: large and effectively
  //    immutable per URL (re-uploads get new paths).
  {
    matcher: isSupabaseStoragePublicObject,
    handler: new CacheFirst({
      cacheName: "catalog-images",
      plugins: [
        new CacheableResponsePlugin({
          statuses: CATALOG_IMAGE_CACHEABLE_STATUSES,
        }),
        new ExpirationPlugin({
          maxEntries: CATALOG_IMAGE_MAX_ENTRIES,
          maxAgeSeconds: CATALOG_IMAGE_MAX_AGE_SECONDS,
        }),
      ],
    }),
  },
];
