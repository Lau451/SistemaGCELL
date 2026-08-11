import { afterEach, describe, expect, it, vi } from "vitest";
import { unstable_doesMiddlewareMatch } from "next/experimental/testing/server";
import { NextRequest, NextResponse } from "next/server";
import { config, proxy } from "./proxy";

/**
 * `proxy.ts` refreshes a real Supabase session on every matched request
 * (design.md's Data Flow) — exercising the full auth-gate branches
 * against a live Auth service is out of scope for a unit test (that is
 * the one documented manual E2E check, per design.md's Testing
 * Strategy). What IS safely testable without a live network or an
 * awkward mock, using Next's own first-party experimental testing
 * utility (`next/experimental/testing/server`, `v15.1+`), is the
 * declarative `matcher` config: this confirms real requests to
 * `/admin/*` are matched, that `/api/admin/*` is correctly excluded
 * (redirecting a JSON fetch to an HTML login page would be a bug — see
 * the file's own doc comment), and that unrelated public routes are
 * unaffected.
 *
 * The branching logic below (`describe("proxy() auth-gate branching")`)
 * IS safely testable, though: `createProxyClient` is mocked one layer
 * above `@supabase/ssr`, the exact precedent already established by
 * `app/api/admin/products/__tests__/route.test.ts` for the sibling
 * Route Handler. This sidesteps the live-network/`server-only` concerns
 * design.md flags while still exercising `proxy()`'s real decisions —
 * only the live `getClaims()` network call itself remains manual-E2E-only.
 */

const GET_CLAIMS = vi.fn();

function defaultCreateProxyClient() {
  return { auth: { getClaims: GET_CLAIMS } };
}

const CREATE_PROXY_CLIENT = vi.fn(defaultCreateProxyClient);

vi.mock("@/lib/supabase/proxy-client", () => ({
  createProxyClient: (request: NextRequest, response: NextResponse) =>
    CREATE_PROXY_CLIENT(request, response),
}));

describe("proxy.ts matcher config", () => {
  it.each([
    ["/admin", true, "the admin landing path itself"],
    ["/admin/login", true, "the login page (needed for the already-authed bounce)"],
    ["/admin/products", true, "a nested admin route"],
    ["/api/admin/products", false, "excluded: the JSON proxy route handles its own 401"],
    ["/catalog", false, "an unrelated public route"],
    ["/", false, "the public storefront root"],
  ])("matches %s: %s (%s)", (path, expected) => {
    expect(
      unstable_doesMiddlewareMatch({
        config,
        url: `https://gcell.example${path}`,
      }),
    ).toBe(expected);
  });
});

describe("proxy.ts module shape", () => {
  it("exports `proxy` as a function (Next 16's required named export)", () => {
    expect(typeof proxy).toBe("function");
  });
});

/**
 * The real decision matrix `proxy()` makes (read from the source):
 * pathname === "/admin/login" × isAuthenticated, crossed with the
 * `isSafeAdminPath` gate on the `next=` param for the non-login branch.
 * `isAuthenticated` itself is derived as `!error && Boolean(data?.claims)`
 * — an `error` present always wins over `claims` being present, which is
 * the specific defensive-coding detail one of the cases below proves.
 */
describe("proxy() auth-gate branching", () => {
  afterEach(() => {
    vi.clearAllMocks();
    // `clearAllMocks` only clears call history, not an implementation set
    // via `mockImplementation` — restore the default so a test that
    // doesn't need cookie-refresh simulation isn't left depending on
    // whichever prior test happened to run before it.
    CREATE_PROXY_CLIENT.mockImplementation(defaultCreateProxyClient);
  });

  function locationOf(response: NextResponse): URL {
    const location = response.headers.get("location");
    if (!location) {
      throw new Error("expected a redirect response with a Location header");
    }
    return new URL(location);
  }

  it("passes through to render the login form when unauthenticated at /admin/login", async () => {
    GET_CLAIMS.mockResolvedValue({ data: null, error: { message: "invalid_token" } });

    const response = await proxy(new NextRequest("https://gcell.example/admin/login"));

    expect(response.headers.get("location")).toBeNull();
  });

  it("redirects an already-authenticated visit to /admin/login back to /admin, carrying the refreshed session", async () => {
    GET_CLAIMS.mockResolvedValue({ data: { claims: { sub: "admin-1" } }, error: null });
    CREATE_PROXY_CLIENT.mockImplementation((_request, response: NextResponse) => {
      response.cookies.set("sb-refreshed", "token-1");
      response.headers.set("cache-control", "no-store, no-cache");
      return { auth: { getClaims: GET_CLAIMS } };
    });

    const response = await proxy(new NextRequest("https://gcell.example/admin/login"));

    expect(locationOf(response).pathname).toBe("/admin");
    expect(response.cookies.get("sb-refreshed")?.value).toBe("token-1");
    expect(response.headers.get("cache-control")).toBe("no-store, no-cache");
  });

  it("redirects an unauthenticated visit to another admin route to /admin/login with a safe next= param, carrying the refreshed session", async () => {
    GET_CLAIMS.mockResolvedValue({ data: null, error: { message: "invalid_token" } });
    CREATE_PROXY_CLIENT.mockImplementation((_request, response: NextResponse) => {
      response.cookies.set("sb-refreshed", "token-2");
      response.headers.set("cache-control", "no-store, no-cache");
      return { auth: { getClaims: GET_CLAIMS } };
    });

    const response = await proxy(new NextRequest("https://gcell.example/admin/products"));
    const location = locationOf(response);

    expect(location.pathname).toBe("/admin/login");
    expect(location.searchParams.get("next")).toBe("/admin/products");
    expect(response.cookies.get("sb-refreshed")?.value).toBe("token-2");
    expect(response.headers.get("cache-control")).toBe("no-store, no-cache");
  });

  it("drops the next= param when isSafeAdminPath rejects it, rather than forwarding an unsafe value", async () => {
    GET_CLAIMS.mockResolvedValue({ data: null, error: { message: "invalid_token" } });

    // Not reachable through the real matcher (config only matches
    // /admin/:path*), but proxy() is called directly in this unit test —
    // proving isSafeAdminPath is real defense-in-depth here, not dead code.
    const response = await proxy(new NextRequest("https://gcell.example/adminx"));
    const location = locationOf(response);

    expect(location.pathname).toBe("/admin/login");
    expect(location.searchParams.has("next")).toBe(false);
  });

  it("passes through an authenticated visit to another admin route", async () => {
    GET_CLAIMS.mockResolvedValue({ data: { claims: { sub: "admin-1" } }, error: null });

    const response = await proxy(new NextRequest("https://gcell.example/admin/products"));

    expect(response.headers.get("location")).toBeNull();
  });

  it("treats a getClaims() error as unauthenticated even when claims are also present", async () => {
    GET_CLAIMS.mockResolvedValue({
      data: { claims: { sub: "admin-1" } },
      error: { message: "expired" },
    });

    const response = await proxy(new NextRequest("https://gcell.example/admin/products"));
    const location = locationOf(response);

    expect(location.pathname).toBe("/admin/login");
  });
});
