"use client";

/**
 * Interactive color/variant picker for the product detail page. Receives
 * every variant + its images pre-fetched and pre-resolved server-side as
 * props; swapping the selected color only updates local React state —
 * zero additional fetch, verified by `variant-picker.test.tsx` spying on
 * `globalThis.fetch`.
 *
 * Out-of-stock swatches stay visible, clickable, and NOT `disabled` — the
 * spec's "Out-of-Stock Variants Stay Visible and Selectable" requirement.
 * A swatch that were `disabled` would make that color's image and price
 * unreachable, which works against "availability is a real buying
 * signal". Instead, an out-of-stock swatch renders a "Sin stock" badge and
 * remains fully selectable, swapping image/price/stock state like any
 * other variant.
 *
 * @see design.md "Variant / Color Picker"
 */
import { useState } from "react";
import Image from "next/image";
import { cn } from "@/lib/utils";

export interface VariantPickerImage {
  url: string;
  alt: string;
}

export interface VariantPickerVariant {
  id: string;
  color: string;
  price: number;
  inStock: boolean;
  images: VariantPickerImage[];
}

export interface VariantPickerProps {
  variants: VariantPickerVariant[];
  /** Used only when the selected variant has zero images of its own. */
  fallbackImage?: VariantPickerImage | null;
}

const priceFormatter = new Intl.NumberFormat("es-AR", {
  style: "currency",
  currency: "ARS",
  maximumFractionDigits: 0,
});

/** First `in_stock` variant, else the first variant in prop order. */
function pickInitialVariantId(
  variants: VariantPickerVariant[],
): string | undefined {
  return (variants.find((variant) => variant.inStock) ?? variants[0])?.id;
}

export function VariantPicker({
  variants,
  fallbackImage = null,
}: VariantPickerProps) {
  const [selectedVariantId, setSelectedVariantId] = useState<
    string | undefined
  >(() => pickInitialVariantId(variants));

  const selected =
    variants.find((variant) => variant.id === selectedVariantId) ??
    variants[0];

  if (!selected) {
    return null;
  }

  const displayImage = selected.images[0] ?? fallbackImage;

  return (
    <div className="flex flex-col gap-4">
      <div className="bg-muted relative aspect-square w-full max-w-sm overflow-hidden rounded-lg">
        {displayImage ? (
          <Image
            src={displayImage.url}
            alt={displayImage.alt}
            fill
            sizes="(max-width: 640px) 100vw, 384px"
            className="object-cover"
            preload
          />
        ) : (
          <div className="text-muted-foreground flex h-full w-full items-center justify-center text-sm">
            Sin imagen disponible
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <p className="text-xl font-semibold" data-testid="variant-picker-price">
          {priceFormatter.format(selected.price)}
        </p>
        {!selected.inStock && (
          <span
            data-testid="variant-picker-stock-badge"
            className="bg-destructive/10 text-destructive rounded-full px-2 py-0.5 text-xs font-medium"
          >
            Sin stock
          </span>
        )}
      </div>

      <div role="radiogroup" aria-label="Color" className="flex flex-wrap gap-2">
        {variants.map((variant) => {
          const isSelected = variant.id === selected.id;
          return (
            <button
              key={variant.id}
              type="button"
              role="radio"
              aria-checked={isSelected}
              onClick={() => setSelectedVariantId(variant.id)}
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm capitalize transition-colors",
                isSelected
                  ? "border-primary bg-primary/10 font-medium"
                  : "border-border hover:bg-muted",
              )}
            >
              <span>{variant.color}</span>
              {!variant.inStock && (
                <span className="bg-muted-foreground/20 rounded-full px-1.5 py-0.5 text-[0.65rem] font-medium uppercase">
                  Sin stock
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
