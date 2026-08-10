/**
 * Shared data-fetch + derive logic for the catalog listing, rendered
 * identically by `/` and `/catalog`. Deliberately NOT a `page.tsx` file:
 * Next's route-export validator only allows a fixed set of named exports
 * (`default`, `revalidate`, `metadata`, ...) from a page module, so this
 * extra async helper lives in its own module that both pages import.
 *
 * This PR (Phase 2) renders the full first page of products with no
 * search/filter UI — that lands in Phase 3 alongside `/api/catalog`.
 *
 * @see design.md "Data Flow", "Decision: No generateStaticParams; reads
 * never throw".
 */
import type { ProductCardProps } from "@/components/catalog/product-card";
import { CatalogListingView } from "@/components/catalog/catalog-listing-view";
import { deriveListingCard } from "@/lib/catalog/derive";
import {
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

  const [variantsResult, imagesResult] = await Promise.all([
    listVariantsForProducts(client, productIds),
    listImagesForProducts(client, productIds),
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
      priceFrom: card.priceFrom,
      hasPriceRange: card.hasPriceRange,
      imageUrl: card.heroImage
        ? toPublicPhotoUrl(supabaseUrl, card.heroImage.storage_path)
        : null,
      imageAlt: card.heroImage?.alt_text ?? card.name,
    };
  });

  return <CatalogListingView products={cards} />;
}
