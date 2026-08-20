/**
 * Listing card: image, name, and "single price" vs "Desde {min}" price
 * display. Pure/presentational — all data (including the resolved public
 * image URL) is pre-computed by the `page.tsx` that renders this grid.
 *
 * @see design.md "Decision: UI copy in Spanish, code in English" for the
 * `Intl.NumberFormat("es-AR", ...)` price formatting.
 */
import Image from "next/image";
import Link from "next/link";
import { ImageOff } from "lucide-react";

const priceFormatter = new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "ARS",
  maximumFractionDigits: 0,
});

export interface ProductCardProps {
  slug: string;
  name: string;
  priceFrom: number;
  hasPriceRange: boolean;
  imageUrl: string | null;
  imageAlt: string;
  /** Optional AI-assisted blurb (D3). Never assumes the 160-char server
   *  cap — `line-clamp-2` truncates visually instead. */
  shortDescription?: string | null;
}

export function ProductCard({
  slug,
  name,
  priceFrom,
  hasPriceRange,
  imageUrl,
  imageAlt,
  shortDescription,
}: ProductCardProps) {
  return (
    <Link
      href={`/product/${slug}`}
      data-testid="product-card"
      className="group border-border hover:border-primary flex flex-col overflow-hidden rounded-lg border transition-colors"
    >
      <div className="bg-muted relative aspect-square w-full">
        {imageUrl ? (
          <Image
            src={imageUrl}
            alt={imageAlt}
            fill
            sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
            className="object-cover transition-transform group-hover:scale-105"
          />
        ) : (
          <div className="text-muted-foreground flex h-full w-full items-center justify-center">
            <ImageOff aria-hidden="true" className="size-8" />
          </div>
        )}
      </div>
      <div className="flex flex-col gap-1 p-3">
        <h3 className="text-sm font-medium">{name}</h3>
        <p className="text-sm font-semibold" data-testid="product-card-price">
          {hasPriceRange ? "Desde " : ""}
          {priceFormatter.format(priceFrom)}
        </p>
        {shortDescription ? (
          <p
            className="text-muted-foreground line-clamp-2 text-xs"
            data-testid="product-card-blurb"
          >
            {shortDescription}
          </p>
        ) : null}
      </div>
    </Link>
  );
}
