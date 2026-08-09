import { describe, expect, it } from "vitest";
import { NetworkFirst, NetworkOnly, type RouteMatchCallbackOptions } from "serwist";
import { catalogRuntimeCaching } from "@/lib/pwa/runtime-caching";

/**
 * Builds the minimal `RouteMatchCallbackOptions`-shaped object a Serwist
 * matcher receives, for a given request path/method.
 */
function matchOptionsFor(path: string, method = "GET"): RouteMatchCallbackOptions {
  const url = new URL(`https://gcell.example${path}`);
  return {
    url,
    request: new Request(url, { method }),
    sameOrigin: true,
  } as RouteMatchCallbackOptions;
}

function findFirstMatch(path: string, method = "GET") {
  const options = matchOptionsFor(path, method);
  return catalogRuntimeCaching.find((entry) => {
    const matcher = entry.matcher;
    if (typeof matcher !== "function") {
      throw new Error("Expected a function matcher");
    }
    return Boolean(matcher(options));
  });
}

describe("catalogRuntimeCaching", () => {
  it("routes any GET request under /admin to a NetworkOnly handler", () => {
    const entry = findFirstMatch("/admin/products");

    expect(entry).toBeDefined();
    expect(entry?.handler).toBeInstanceOf(NetworkOnly);
  });

  it("routes admin sub-routes and non-GET requests to NetworkOnly before any other matcher can claim them", () => {
    const adminSubRoute = findFirstMatch("/admin/products/42/edit");
    const nonGetCatalogRequest = findFirstMatch("/catalog/cases", "POST");

    expect(adminSubRoute?.handler).toBeInstanceOf(NetworkOnly);
    expect(nonGetCatalogRequest?.handler).toBeInstanceOf(NetworkOnly);
  });

  it("never routes a GET /admin request to a caching-capable handler like NetworkFirst", () => {
    const entry = findFirstMatch("/admin/orders");

    expect(entry?.handler).not.toBeInstanceOf(NetworkFirst);
  });

  it("does not route public catalog GET requests to NetworkOnly", () => {
    const entry = findFirstMatch("/catalog/fundas");

    expect(entry?.handler).toBeInstanceOf(NetworkFirst);
    expect(entry?.handler).not.toBeInstanceOf(NetworkOnly);
  });
});
