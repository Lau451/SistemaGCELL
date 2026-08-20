/**
 * Pure derivations over already-fetched catalog rows: price-from,
 * hero-image fallback, and the composed listing-card shape. Zero
 * Next.js/Supabase imports — `queries.ts` (Phase 2) fetches rows, this
 * module turns them into display data.
 *
 * @see design.md "Query Shapes" — hero-image fallback rationale.
 */
import type {
  CatalogImageRow,
  CatalogProductRow,
  CatalogVariantRow,
} from "./types";

export interface CatalogListingCard {
  id: string;
  slug: string;
  name: string;
  shortDescription: string | null;
  priceFrom: number;
  hasPriceRange: boolean;
  inStock: boolean;
  colors: string[];
  heroImage: CatalogImageRow | null;
}

export interface DeriveListingCardInput {
  product: CatalogProductRow;
  variants: CatalogVariantRow[];
  images: CatalogImageRow[];
}

export function derivePriceFrom(variants: CatalogVariantRow[]): {
  priceFrom: number;
  hasPriceRange: boolean;
} {
  if (variants.length === 0) {
    return { priceFrom: 0, hasPriceRange: false };
  }

  const prices = variants.map((variant) => variant.price);
  const priceFrom = Math.min(...prices);
  const hasPriceRange = prices.some((price) => price !== priceFrom);

  return { priceFrom, hasPriceRange };
}

/** First `in_stock` variant, else the first variant in input order. */
function pickDefaultVariant(
  variants: CatalogVariantRow[],
): CatalogVariantRow | null {
  if (variants.length === 0) return null;
  return variants.find((variant) => variant.in_stock) ?? variants[0];
}

function sortBySortOrder(images: CatalogImageRow[]): CatalogImageRow[] {
  return [...images].sort((a, b) => a.sort_order - b.sort_order);
}

/**
 * Hero-image fallback chain (seed-verified: `seed.sql` inserts zero
 * `variant_id IS NULL` rows, so every real product actually takes the
 * second branch):
 *   1. lowest-`sort_order` image with `variant_id === null`
 *   2. else the default variant's lowest-`sort_order` image
 *   3. else `null` — the presentational layer renders a local placeholder
 */
export function deriveHeroImage(
  variants: CatalogVariantRow[],
  images: CatalogImageRow[],
): CatalogImageRow | null {
  const heroCandidates = sortBySortOrder(
    images.filter((image) => image.variant_id === null),
  );
  if (heroCandidates.length > 0) {
    return heroCandidates[0];
  }

  const defaultVariant = pickDefaultVariant(variants);
  if (defaultVariant !== null) {
    const variantImages = sortBySortOrder(
      images.filter((image) => image.variant_id === defaultVariant.id),
    );
    if (variantImages.length > 0) {
      return variantImages[0];
    }
  }

  return null;
}

export function deriveListingCard(
  input: DeriveListingCardInput,
): CatalogListingCard {
  const { product, variants, images } = input;
  const { priceFrom, hasPriceRange } = derivePriceFrom(variants);
  const inStock = variants.some((variant) => variant.in_stock);
  const colors = variants.map((variant) => variant.color);
  const heroImage = deriveHeroImage(variants, images);

  return {
    id: product.id,
    slug: product.slug,
    name: product.name,
    shortDescription: product.short_description,
    priceFrom,
    hasPriceRange,
    inStock,
    colors,
    heroImage,
  };
}
