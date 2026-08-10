/**
 * Pure builder for `next.config.ts`'s `images.remotePatterns` entry. Zero
 * imports so `next.config.ts` can import it via a relative path and Vitest
 * can test it directly, with no Next.js runtime involved.
 *
 * The explicit object form (not Next 16's `new URL(...)` shorthand) is
 * used so `search` can be pinned to `""` — omitting `search` implies the
 * `**` wildcard, per `next/dist/docs/.../components/image.md`.
 *
 * @see design.md "`next.config.ts` — `images.remotePatterns`"
 */

export const PRODUCT_PHOTO_PATHNAME =
  "/storage/v1/object/public/product-photos/**";

export interface ProductPhotoRemotePattern {
  protocol: "http" | "https";
  hostname: string;
  port: string;
  pathname: string;
  search: string;
}

export function buildProductPhotoPattern(
  rawSupabaseUrl: string,
): ProductPhotoRemotePattern {
  // `new URL` throws early on a malformed env value instead of silently
  // producing a broken remotePattern.
  const url = new URL(rawSupabaseUrl);
  return {
    protocol: url.protocol.replace(":", "") as "http" | "https",
    hostname: url.hostname,
    port: url.port,
    pathname: PRODUCT_PHOTO_PATHNAME,
    search: "",
  };
}
