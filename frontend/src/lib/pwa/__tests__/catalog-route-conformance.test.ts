import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  NetworkFirst,
  NetworkOnly,
  StaleWhileRevalidate,
  type RouteMatchCallbackOptions,
} from "serwist";
import { catalogRuntimeCaching } from "@/lib/pwa/runtime-caching";

/**
 * Confirms every real route this change introduces across all three PRs
 * (`/`, `/catalog`, `/product/<slug>` in PR2; `/api/catalog` in PR3;
 * `/admin`, `/admin/login`, `/admin/products`, `/api/admin/products` in
 * `admin-panel-auth` PR2/PR3) matches the existing, PINNED matchers in
 * `runtime-caching.ts` — and that the file itself is byte-identical to
 * its pre-change state EXCEPT for one deliberate, minimal extension:
 * `isAdminOrMutatingRequest` gained an `/api/admin` prefix check,
 * mirroring the existing `isCatalogApiRead`/`CATALOG_API_PREFIX`
 * pattern already in this file. This was necessary, not optional:
 * `/api/admin/*` and `/admin/*` are different path prefixes, and
 * `proxy.ts`'s own matcher (`/admin/:path*`) deliberately EXCLUDES
 * `/api/admin/*` so the JSON proxy route can return its own `401`
 * instead of an HTML redirect — the two matchers have opposite
 * requirements for this one path, so the route cannot simply be
 * renamed under `/admin/*` to dodge a `runtime-caching.ts` edit.
 * The PRE_CHANGE_SHA256 below was recomputed after this edit and
 * pins the new content, so any FURTHER edit still fails this test.
 *
 * PR4 (`admin-product-crud`) adds `/admin/products/new`,
 * `/admin/products/{id}`, and `/api/admin/products/{id}` — all covered
 * by the SAME `isAdminOrMutatingRequest` prefix checks above (`/admin/`
 * and `/api/admin`), so ZERO further `runtime-caching.ts` edit was
 * needed; the SHA256 pin is unchanged from `admin-panel-auth`'s PR3.
 */

// Pins `runtime-caching.ts` as of the ONE deliberate `/api/admin` prefix
// extension this PR made (see the file-level comment above for why). Any
// FURTHER, undocumented edit to this file still fails this test.
//
// Pinned against LF-normalized bytes, not the on-disk bytes: Windows
// checkouts materialize this file with CRLF line endings (git's
// core.autocrlf=true), but the repository stores LF and Linux CI checks
// out LF unchanged -- hashing the raw on-disk buffer made this test
// pass locally on Windows and fail on every Linux CI run.
const PRE_CHANGE_SHA256 =
  "cb2278e82f15f8299b651eb025ee8ab015642014dd9ff32c67d63a90895b6454";

const RUNTIME_CACHING_PATH = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "runtime-caching.ts",
);

function matchOptionsFor(path: string): RouteMatchCallbackOptions {
  const url = new URL(`https://gcell.example${path}`);
  return {
    url,
    request: new Request(url, { method: "GET" }),
    sameOrigin: true,
  } as RouteMatchCallbackOptions;
}

describe("runtime-caching.ts conformance for public-catalog-screens routes", () => {
  it("matches the pinned content (only the documented /api/admin extension)", () => {
    // Normalize CRLF -> LF before hashing: the repository stores LF, but a
    // Windows working tree with core.autocrlf=true materializes CRLF on
    // disk. Hashing raw on-disk bytes makes the pin OS-dependent; hashing
    // the LF-normalized text makes it stable everywhere.
    const source = readFileSync(RUNTIME_CACHING_PATH, "utf8").replace(/\r\n/g, "\n");
    const hash = createHash("sha256").update(source).digest("hex");
    expect(hash).toBe(PRE_CHANGE_SHA256);
  });

  it.each([
    ["/", "listing at the root"],
    ["/catalog", "the catalog alias"],
    ["/product/fundas-iphone-15", "a product detail page"],
  ])("matches the NetworkFirst catalog-pages handler for %s (%s)", (path) => {
    const options = matchOptionsFor(path);
    const entry = catalogRuntimeCaching.find((candidate) => {
      const matcher = candidate.matcher;
      if (typeof matcher !== "function") {
        throw new Error("Expected a function matcher");
      }
      return Boolean(matcher(options));
    });

    expect(entry).toBeDefined();
    expect(entry?.handler).toBeInstanceOf(NetworkFirst);
  });

  it("matches the StaleWhileRevalidate catalog-api handler for /api/catalog (isCatalogApiRead)", () => {
    const options = matchOptionsFor("/api/catalog?q=funda");
    const entry = catalogRuntimeCaching.find((candidate) => {
      const matcher = candidate.matcher;
      if (typeof matcher !== "function") {
        throw new Error("Expected a function matcher");
      }
      return Boolean(matcher(options));
    });

    expect(entry).toBeDefined();
    expect(entry?.handler).toBeInstanceOf(StaleWhileRevalidate);
  });

  it.each([
    ["/admin", "the admin landing page"],
    ["/admin/login", "the login page — must never land in a shared cache"],
    ["/admin/products", "the admin products list page"],
    ["/admin/products/new", "the create-product page (PR4)"],
    [
      "/admin/products/11111111-1111-1111-1111-111111111111",
      "the edit-product page (PR4)",
    ],
    ["/api/admin/products", "the server-to-server admin proxy route"],
    [
      "/api/admin/products/11111111-1111-1111-1111-111111111111",
      "the single-product admin proxy route (PR4)",
    ],
  ])(
    "matches the NetworkOnly admin handler for %s (%s)",
    (path) => {
      const options = matchOptionsFor(path);
      const entry = catalogRuntimeCaching.find((candidate) => {
        const matcher = candidate.matcher;
        if (typeof matcher !== "function") {
          throw new Error("Expected a function matcher");
        }
        return Boolean(matcher(options));
      });

      expect(entry).toBeDefined();
      expect(entry?.handler).toBeInstanceOf(NetworkOnly);
    },
  );
});
