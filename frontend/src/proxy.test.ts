import { describe, expect, it } from "vitest";
import { unstable_doesMiddlewareMatch } from "next/experimental/testing/server";
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
 */
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
