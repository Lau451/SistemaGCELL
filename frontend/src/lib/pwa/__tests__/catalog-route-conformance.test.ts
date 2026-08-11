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
 */

// Pins `runtime-caching.ts` as of the ONE deliberate `/api/admin` prefix
// extension this PR made (see the file-level comment above for why). Any
// FURTHER, undocumented edit to this file still fails this test.
const PRE_CHANGE_SHA256 =
  "4c6f7cdb2a0f76166c0cd2dd7fe556b7d62fc6ef40a4a0614ea8758fed9573c4";

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
    const source = readFileSync(RUNTIME_CACHING_PATH);
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
    ["/admin/products", "the admin products proof page"],
    ["/api/admin/products", "the server-to-server admin proxy route"],
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
