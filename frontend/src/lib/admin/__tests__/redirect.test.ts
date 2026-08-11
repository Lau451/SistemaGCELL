import { describe, expect, it } from "vitest";
import { isSafeAdminPath } from "@/lib/admin/redirect";

/**
 * `isSafeAdminPath` guards the `next=` return-URL query param used by
 * `proxy.ts` and the login Server Action (design.md "Open-redirect
 * guard"). This is a real open-redirect boundary, not a cosmetic check:
 * it must reject protocol-relative URLs (`//evil.com`), the
 * backslash-as-slash browser-normalization trick (`/\evil.com`),
 * absolute off-origin URLs (`https://evil`), and string-prefix
 * look-alikes that are not genuinely under `/admin` (`/adminx`) or are a
 * different section entirely (`/catalog`) — while still accepting the
 * exact landing path and any real `/admin/*` path with a query string.
 */
describe("isSafeAdminPath", () => {
  it.each([
    ["//evil.com", "protocol-relative URL"],
    ["/\\evil.com", "backslash-as-slash open-redirect trick"],
    ["https://evil", "absolute off-origin URL"],
    ["/adminx", "string-prefix look-alike, not genuinely under /admin"],
    ["/catalog", "a different, non-admin section"],
  ])("rejects %s (%s)", (candidate) => {
    expect(isSafeAdminPath(candidate)).toBe(false);
  });

  it.each([
    ["/admin", "the exact admin landing path"],
    ["/admin/products?x=1", "a real admin path with a query string"],
  ])("accepts %s (%s)", (candidate) => {
    expect(isSafeAdminPath(candidate)).toBe(true);
  });

  it.each([[""], [null], [undefined]])(
    "rejects empty/nullish input (%j)",
    (candidate) => {
      expect(isSafeAdminPath(candidate)).toBe(false);
    },
  );
});
