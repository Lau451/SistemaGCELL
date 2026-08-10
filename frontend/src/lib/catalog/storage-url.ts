/**
 * `storage_path` (bucket-relative, e.g. `fundas-iphone-15/negro.jpg`) to a
 * public Supabase Storage URL. Pure — takes the Supabase URL as a
 * parameter instead of reading `process.env` so it stays trivially
 * testable and reusable from both server and (future) client code.
 *
 * @see design.md "Public image URL"
 */

export const PRODUCT_PHOTOS_BUCKET = "product-photos";

export function toPublicPhotoUrl(
  supabaseUrl: string,
  storagePath: string,
): string {
  const base = supabaseUrl.replace(/\/+$/, "");
  const path = storagePath.replace(/^\/+/, "");
  return `${base}/storage/v1/object/public/${PRODUCT_PHOTOS_BUCKET}/${path}`;
}
