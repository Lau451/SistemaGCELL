import { describe, expect, it } from "vitest";
import {
  deriveHeroImage,
  deriveListingCard,
  derivePriceFrom,
} from "./derive";
import type {
  CatalogImageRow,
  CatalogProductRow,
  CatalogVariantRow,
} from "./types";

const product: CatalogProductRow = {
  id: "product-1",
  slug: "fundas-iphone-15",
  name: "Funda iPhone 15",
  description: null,
  created_at: "2026-01-01T00:00:00.000Z",
};

function variant(overrides: Partial<CatalogVariantRow>): CatalogVariantRow {
  return {
    id: "variant-1",
    product_id: "product-1",
    phone_model: "iPhone 15",
    color: "negro",
    price: 1000,
    in_stock: true,
    ...overrides,
  };
}

function image(overrides: Partial<CatalogImageRow>): CatalogImageRow {
  return {
    id: "image-1",
    product_id: "product-1",
    variant_id: null,
    storage_path: "fundas-iphone-15/hero.jpg",
    alt_text: null,
    sort_order: 0,
    ...overrides,
  };
}

describe("derivePriceFrom", () => {
  it("has no price range when every variant shares the same price", () => {
    const variants = [
      variant({ id: "v1", price: 1000 }),
      variant({ id: "v2", price: 1000 }),
    ];

    expect(derivePriceFrom(variants)).toEqual({
      priceFrom: 1000,
      hasPriceRange: false,
    });
  });

  it("reports a price range when variants have differing prices", () => {
    const variants = [
      variant({ id: "v1", price: 1200 }),
      variant({ id: "v2", price: 1000 }),
      variant({ id: "v3", price: 1500 }),
    ];

    expect(derivePriceFrom(variants)).toEqual({
      priceFrom: 1000,
      hasPriceRange: true,
    });
  });
});

describe("deriveHeroImage", () => {
  it("prefers the lowest-sort_order image with a null variant_id", () => {
    const variants = [variant({ id: "v1" })];
    const images = [
      image({ id: "hero-2", variant_id: null, sort_order: 1 }),
      image({ id: "hero-1", variant_id: null, sort_order: 0 }),
      image({ id: "variant-img", variant_id: "v1", sort_order: 0 }),
    ];

    expect(deriveHeroImage(variants, images)?.id).toBe("hero-1");
  });

  it("falls back to the default variant's first image when no hero row exists", () => {
    // Matches the real seed shape: seed.sql inserts zero variant_id IS NULL
    // rows, so this is the path every real product actually takes.
    const variants = [
      variant({ id: "v1", in_stock: true }),
      variant({ id: "v2", in_stock: true }),
    ];
    const images = [
      image({
        id: "v1-img-2",
        variant_id: "v1",
        sort_order: 1,
      }),
      image({
        id: "v1-img-1",
        variant_id: "v1",
        sort_order: 0,
      }),
      image({
        id: "v2-img-1",
        variant_id: "v2",
        sort_order: 0,
      }),
    ];

    expect(deriveHeroImage(variants, images)?.id).toBe("v1-img-1");
  });

  it("falls back to the first in-stock variant, skipping an out-of-stock earlier variant", () => {
    const variants = [
      variant({ id: "v1", in_stock: false }),
      variant({ id: "v2", in_stock: true }),
    ];
    const images = [
      image({ id: "v1-img", variant_id: "v1", sort_order: 0 }),
      image({ id: "v2-img", variant_id: "v2", sort_order: 0 }),
    ];

    expect(deriveHeroImage(variants, images)?.id).toBe("v2-img");
  });

  it("returns null (placeholder) when no hero row and no variant image exist", () => {
    const variants = [variant({ id: "v1" })];
    const images: CatalogImageRow[] = [];

    expect(deriveHeroImage(variants, images)).toBeNull();
  });
});

describe("deriveListingCard", () => {
  it("composes product, price-from, stock, colors, and hero image", () => {
    const variants = [
      variant({ id: "v1", color: "negro", price: 1000, in_stock: true }),
      variant({ id: "v2", color: "transparente", price: 1200, in_stock: false }),
    ];
    const images = [image({ id: "hero", variant_id: null, sort_order: 0 })];

    const card = deriveListingCard({ product, variants, images });

    expect(card).toEqual({
      id: "product-1",
      slug: "fundas-iphone-15",
      name: "Funda iPhone 15",
      priceFrom: 1000,
      hasPriceRange: true,
      inStock: true,
      colors: ["negro", "transparente"],
      heroImage: images[0],
    });
  });

  it("reports inStock false when every variant is out of stock", () => {
    const variants = [variant({ id: "v1", in_stock: false })];
    const card = deriveListingCard({ product, variants, images: [] });

    expect(card.inStock).toBe(false);
  });
});
