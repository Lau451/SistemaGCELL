import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import {
  NetworkFirst,
  StaleWhileRevalidate,
  type RouteMatchCallbackOptions,
} from "serwist";
import { catalogRuntimeCaching } from "@/lib/pwa/runtime-caching";

/**
 * Confirms every real route this change introduces across all three PRs
 * (`/`, `/catalog`, `/product/<slug>` in PR2; `/api/catalog` in PR3)
 * matches the existing, PINNED matchers in `runtime-caching.ts` — and that
 * the file itself is byte-identical to its pre-change state. Spec:
 * "Catalog Routes Conform to the Pinned Runtime-Caching Matcher" /
 * "API Routes Conform to the Pinned Runtime-Caching Matcher" — this file
 * MUST NOT be modified to accommodate a route shape.
 */

// Captured from `runtime-caching.ts` before this change touched anything
// under `app/(public)/`. If this hash ever changes, the file was edited —
// which the spec forbids for this capability.
const PRE_CHANGE_SHA256 =
  "480f81465825d9af7615a16772e55e78eb383f0815e403cc8bd8cc5ba98bc33c";

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
  it("is byte-identical to its pre-change state", () => {
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
});
