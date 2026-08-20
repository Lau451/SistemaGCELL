/**
 * Shared data-fetch + derive logic for the catalog listing, rendered
 * identically by `/` and `/catalog`. Deliberately NOT a `page.tsx` file:
 * Next's route-export validator only allows a fixed set of named exports
 * (`default`, `revalidate`, `metadata`, ...) from a page module, so this
 * extra async helper lives in its own module that both pages import.
 *
 * Renders the server-fetched first page as `CatalogFilters`' initial
 * props whenever the catalog has products — the ISR-rendered first page
 * stays untouched (`revalidate = 300` is unaffected, nothing here calls
 * `cookies()`) and `CatalogFilters` (PR3) takes over search/filter/
 * pagination client-side via `/api/catalog`. Per design.md's Empty/
 * No-Results/Error States table, filter UI is hidden for the
 * `empty-catalog`/`error` states, so those still render the plain
 * `CatalogListingView`.
 *
 * @see design.md "Data Flow", "Decision: No generateStaticParams; reads
 * never throw", "Empty / No-Results / Error States".
 */
import { CatalogFilters } from "@/components/catalog/catalog-filters";
import { CatalogListingView } from "@/components/catalog/catalog-listing-view";
import type { ProductCardProps } from "@/components/catalog/product-card";
import { deriveListingCard } from "@/lib/catalog/derive";
import {
  getCatalogFilterOptions,
  listCatalogProducts,
  listImagesForProducts,
  listVariantsForProducts,
} from "@/lib/catalog/queries";
import { toPublicPhotoUrl } from "@/lib/catalog/storage-url";
import { getCatalogSupabaseEnv } from "@/lib/supabase/env";
import { createAnonCatalogClient } from "@/lib/supabase/server";

const LISTING_PAGE_SIZE = 12;

export async function CatalogListingPageContent() {
  const client = createAnonCatalogClient();
  const { url: supabaseUrl } = getCatalogSupabaseEnv();

  const listingResult = await listCatalogProducts(client, {
    q: null,
    productIds: null,
    page: 1,
    limit: LISTING_PAGE_SIZE,
  });

  if (!listingResult.ok) {
    return <CatalogListingView products={[]} emptyStateVariant="error" />;
  }

  const { products, total } = listingResult.data;

  if (total === 0 || products.length === 0) {
    return (
      <CatalogListingView products={[]} emptyStateVariant="empty-catalog" />
    );
  }

  const productIds = products.map((product) => product.id);

  const [variantsResult, imagesResult, filterOptionsResult] =
    await Promise.all([
      listVariantsForProducts(client, productIds),
      listImagesForProducts(client, productIds),
      getCatalogFilterOptions(client),
    ]);

  if (!variantsResult.ok || !imagesResult.ok) {
    return <CatalogListingView products={[]} emptyStateVariant="error" />;
  }

  const variants = variantsResult.data;
  const images = imagesResult.data;

  const cards: ProductCardProps[] = products.map((product) => {
    const productVariants = variants.filter(
      (variant) => variant.product_id === product.id,
    );
    const productImages = images.filter(
      (image) => image.product_id === product.id,
    );
    const card = deriveListingCard({
      product,
      variants: productVariants,
      images: productImages,
    });

    return {
      slug: card.slug,
      name: card.name,
      shortDescription: card.shortDescription,
      priceFrom: card.priceFrom,
      hasPriceRange: card.hasPriceRange,
      imageUrl: card.heroImage
        ? toPublicPhotoUrl(supabaseUrl, card.heroImage.storage_path)
        : null,
      imageAlt: card.heroImage?.alt_text ?? card.name,
    };
  });

  // Filter dropdown options are a non-fatal enhancement: if this query
  // fails, the initial listing still renders and search-by-text still
  // works through /api/catalog, just with empty model/color dropdowns.
  const filterOptions = filterOptionsResult.ok
    ? filterOptionsResult.data
    : { models: [], colors: [] };

  return (
    <CatalogFilters initialItems={cards} initialFilters={filterOptions} />
  );
}
