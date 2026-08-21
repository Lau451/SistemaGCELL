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
import { Card, CardContent } from "@/components/ui/card";

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
    <Link href={`/product/${slug}`} data-testid="product-card" className="group block">
      <Card className="h-full gap-0 overflow-hidden py-0 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:border-brand-primary/40 hover:shadow-md">
        <div className="bg-muted relative aspect-square w-full overflow-hidden">
          {imageUrl ? (
            <Image
              src={imageUrl}
              alt={imageAlt}
              fill
              sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
              className="object-cover transition-transform duration-300 group-hover:scale-105"
            />
          ) : (
            <div className="text-muted-foreground flex h-full w-full items-center justify-center">
              <ImageOff aria-hidden="true" className="size-8" />
            </div>
          )}
        </div>
        <CardContent className="flex flex-col gap-1 px-3 py-3">
          <h3 className="font-heading text-sm font-medium text-foreground">
            {name}
          </h3>
          <p
            className="text-sm font-semibold text-brand-primary"
            data-testid="product-card-price"
          >
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
        </CardContent>
      </Card>
    </Link>
  );
}
