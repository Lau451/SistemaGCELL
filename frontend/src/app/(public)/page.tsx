/**
 * `/` — catalog listing. Classic ISR (`revalidate = 300`): uses
 * `createAnonCatalogClient()`, which never calls `cookies()`, so this
 * route stays statically generated instead of opting into dynamic
 * rendering. Fetch + derive logic lives in `catalog-listing-content.tsx`
 * so `/catalog` (the canonical alias) can render the exact same output
 * without duplicating it.
 */
import { CatalogListingPageContent } from "./catalog-listing-content";

export const revalidate = 300;

export default async function CatalogListingPage() {
  return <CatalogListingPageContent />;
}
