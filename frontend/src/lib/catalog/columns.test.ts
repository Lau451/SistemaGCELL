import { describe, expect, it } from "vitest";
import {
  CATALOG_IMAGE_COLUMNS,
  CATALOG_PRODUCT_COLUMNS,
  CATALOG_RELATIONS,
  CATALOG_VARIANT_COLUMNS,
} from "./columns";

// Tokens that must never appear in a public catalog column list. They exist
// only on base tables (`product_variants.cost`) or the internal-only
// `variant_stock_levels` view, neither of which anon/authenticated can read.
const FORBIDDEN_TOKENS = [
  "cost",
  "quantity",
  "quantity_on_hand",
  "stock_movements",
];

describe("CATALOG_RELATIONS", () => {
  it("allows only the three public catalog views, in the documented order", () => {
    expect(CATALOG_RELATIONS).toEqual([
      "catalog_products",
      "catalog_variants",
      "catalog_product_images",
    ]);
  });

  it("never includes a base table name", () => {
    expect(CATALOG_RELATIONS).not.toContain("products");
    expect(CATALOG_RELATIONS).not.toContain("product_variants");
    expect(CATALOG_RELATIONS).not.toContain("product_images");
    expect(CATALOG_RELATIONS).not.toContain("variant_stock_levels");
  });
});

describe("catalog column constants", () => {
  it("CATALOG_PRODUCT_COLUMNS matches the catalog_products view exactly", () => {
    expect(CATALOG_PRODUCT_COLUMNS.split(",")).toEqual([
      "id",
      "slug",
      "name",
      "description",
      "created_at",
    ]);
  });

  it("CATALOG_VARIANT_COLUMNS matches the catalog_variants view exactly", () => {
    expect(CATALOG_VARIANT_COLUMNS.split(",")).toEqual([
      "id",
      "product_id",
      "phone_model",
      "color",
      "price",
      "in_stock",
    ]);
  });

  it("CATALOG_IMAGE_COLUMNS matches the catalog_product_images view exactly", () => {
    expect(CATALOG_IMAGE_COLUMNS.split(",")).toEqual([
      "id",
      "product_id",
      "variant_id",
      "storage_path",
      "alt_text",
      "sort_order",
    ]);
  });

  it("never exposes a cost or exact-stock-quantity token", () => {
    const allTokens = [
      ...CATALOG_PRODUCT_COLUMNS.split(","),
      ...CATALOG_VARIANT_COLUMNS.split(","),
      ...CATALOG_IMAGE_COLUMNS.split(","),
    ];

    for (const forbidden of FORBIDDEN_TOKENS) {
      expect(allTokens).not.toContain(forbidden);
    }
  });
});
