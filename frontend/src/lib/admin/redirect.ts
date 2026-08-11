/**
 * Open-redirect guard for the `next=` return-URL query param used by
 * `proxy.ts` (unauthenticated redirect) and `signInAction` (post-login
 * redirect). See design.md "Open-redirect guard".
 *
 * A naive `next.startsWith("/admin")` string check is NOT sufficient:
 * `/adminx` passes that check but is not genuinely under `/admin`, and
 * browser-normalization tricks (`//evil.com`, `/\evil.com` — a backslash
 * is treated the same as a forward slash for special schemes per the
 * WHATWG URL spec) can smuggle an off-origin authority through a
 * leading-slash string that *looks* path-relative.
 *
 * Instead, this parses `next` against a fixed, arbitrary same-scheme
 * base and rejects anything that resolves to a different origin — which
 * catches protocol-relative URLs and the backslash trick uniformly,
 * since both end up rewriting the authority during WHATWG parsing —
 * then checks the *parsed* pathname (not the raw string) against the
 * `/admin` prefix.
 */

const ADMIN_LANDING_PATH = "/admin";

// Only used to give `new URL()` a same-scheme base to resolve `next`
// against; never sent anywhere. Any fixed http(s) origin works here.
const GUARD_BASE_ORIGIN = "http://admin-panel.internal";

export function isSafeAdminPath(
  next: string | null | undefined,
): boolean {
  if (!next || !next.startsWith("/")) {
    return false;
  }

  let parsed: URL;
  try {
    parsed = new URL(next, GUARD_BASE_ORIGIN);
  } catch {
    return false;
  }

  if (parsed.origin !== GUARD_BASE_ORIGIN) {
    return false;
  }

  return (
    parsed.pathname === ADMIN_LANDING_PATH ||
    parsed.pathname.startsWith(`${ADMIN_LANDING_PATH}/`)
  );
}
