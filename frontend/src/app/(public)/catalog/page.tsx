/**
 * `/catalog` — alias of `/`, same content, canonical URL points back to
 * `/`. A `redirect()` was rejected in design.md: it would drop `?q=`/
 * `?model=` deep links once Phase 3 adds search/filter params.
 */
import type { Metadata } from "next";
import { CatalogListingPageContent } from "../catalog-listing-content";

export const revalidate = 300;

export const metadata: Metadata = {
  alternates: {
    canonical: "/",
  },
};

export default async function CatalogAliasPage() {
  return <CatalogListingPageContent />;
}
