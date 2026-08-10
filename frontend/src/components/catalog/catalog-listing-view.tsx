/**
 * Pure grid composing `ProductCard`s + the deliberate empty/no-results/
 * error state. The listing `page.tsx` decides `emptyStateVariant` from
 * fetched data (never from a thrown error) and passes already-resolved
 * card props here — this component itself does no fetching.
 *
 * @see design.md "Empty / No-Results / Error States"
 */
import {
  CatalogEmptyState,
  type CatalogEmptyStateVariant,
} from "./catalog-empty-state";
import { ProductCard, type ProductCardProps } from "./product-card";

export interface CatalogListingViewProps {
  products: ProductCardProps[];
  /** Explicit override for the "no-results"/"error" states; defaults to `empty-catalog` when `products` is empty. */
  emptyStateVariant?: CatalogEmptyStateVariant | null;
}

export function CatalogListingView({
  products,
  emptyStateVariant = null,
}: CatalogListingViewProps) {
  if (emptyStateVariant) {
    return <CatalogEmptyState variant={emptyStateVariant} />;
  }

  if (products.length === 0) {
    return <CatalogEmptyState variant="empty-catalog" />;
  }

  return (
    <div
      data-testid="catalog-listing-grid"
      className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
    >
      {products.map((product) => (
        <ProductCard key={product.slug} {...product} />
      ))}
    </div>
  );
}
