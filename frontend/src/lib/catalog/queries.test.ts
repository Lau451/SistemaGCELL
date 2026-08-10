import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { SupabaseClient } from "@supabase/supabase-js";
import {
  getCatalogFilterOptions,
  getCatalogProductBySlug,
  listCatalogProducts,
  listImagesForProducts,
  listVariantsForProducts,
  scopeProductIdsByVariant,
} from "./queries";
import {
  CATALOG_IMAGE_COLUMNS,
  CATALOG_PRODUCT_COLUMNS,
  CATALOG_VARIANT_COLUMNS,
} from "./columns";

/**
 * Minimal hand-rolled recording fake for the subset of the PostgREST
 * query-builder chain `queries.ts` actually uses. Every chain method
 * records its call and returns `this`; the builder itself is a thenable
 * (like the real supabase-js builder) so `await`-ing it resolves to the
 * pre-programmed result.
 */
interface RecordedCall {
  method: string;
  args: unknown[];
}

interface FakeQueryBuilder {
  calls: RecordedCall[];
  [method: string]: unknown;
}

function createFakeQueryBuilder(result: {
  data: unknown;
  error: { message: string } | null;
  count?: number | null;
}): FakeQueryBuilder {
  const calls: RecordedCall[] = [];

  const builder: FakeQueryBuilder = { calls };

  for (const method of ["select", "eq", "in", "or", "order", "range"]) {
    builder[method] = (...args: unknown[]) => {
      calls.push({ method, args });
      return builder;
    };
  }

  builder.maybeSingle = () => {
    calls.push({ method: "maybeSingle", args: [] });
    return Promise.resolve(result);
  };

  builder.then = (
    onFulfilled?: (value: typeof result) => unknown,
    onRejected?: (reason: unknown) => unknown,
  ) => Promise.resolve(result).then(onFulfilled, onRejected);

  return builder;
}

function createFakeClient(
  buildersByRelation: Record<string, FakeQueryBuilder>,
) {
  const fromCalls: string[] = [];
  const client = {
    fromCalls,
    from: (relation: string) => {
      fromCalls.push(relation);
      const builder = buildersByRelation[relation];
      if (!builder) {
        throw new Error(`Unexpected relation queried: ${relation}`);
      }
      return builder;
    },
  };
  return client as unknown as SupabaseClient & { fromCalls: string[] };
}

describe("queries.ts source safety", () => {
  const QUERIES_SOURCE_PATH = join(
    dirname(fileURLToPath(import.meta.url)),
    "queries.ts",
  );
  const ALLOWED_SELECT_ARGS = [
    "CATALOG_PRODUCT_COLUMNS",
    "CATALOG_VARIANT_COLUMNS",
    "CATALOG_IMAGE_COLUMNS",
  ];

  it("passes only an exported column constant to every .select( call — never a literal string or select(\"*\")", () => {
    const source = readFileSync(QUERIES_SOURCE_PATH, "utf-8");
    const selectCalls = [...source.matchAll(/\.select\(\s*([A-Za-z0-9_]+)/g)];

    expect(selectCalls.length).toBeGreaterThan(0);
    for (const match of selectCalls) {
      expect(ALLOWED_SELECT_ARGS).toContain(match[1]);
    }
  });

  it("never calls .from( with a literal string — only the typed catalogFrom() helper", () => {
    const source = readFileSync(QUERIES_SOURCE_PATH, "utf-8");
    const literalFromCalls = [...source.matchAll(/(?<!catalog)\.from\(\s*["']/g)];
    expect(literalFromCalls).toHaveLength(0);
  });
});

describe("scopeProductIdsByVariant", () => {
  it("returns null (no scope) without querying when neither model nor color is given", async () => {
    const client = createFakeClient({});

    const result = await scopeProductIdsByVariant(client, {});

    expect(result).toEqual({ ok: true, data: null });
    expect(client.fromCalls).toEqual([]);
  });

  it("queries catalog_variants with the exact column constant and eq() composition for model+color", async () => {
    const builder = createFakeQueryBuilder({
      data: [
        { id: "v1", product_id: "p1", phone_model: "iPhone 15", color: "negro", price: 1, in_stock: true },
        { id: "v2", product_id: "p2", phone_model: "iPhone 15", color: "negro", price: 1, in_stock: true },
        { id: "v3", product_id: "p1", phone_model: "iPhone 15", color: "negro", price: 1, in_stock: true },
      ],
      error: null,
    });
    const client = createFakeClient({ catalog_variants: builder });

    const result = await scopeProductIdsByVariant(client, {
      model: "iPhone 15",
      color: "negro",
    });

    expect(client.fromCalls).toEqual(["catalog_variants"]);
    expect(builder.calls[0]).toEqual({ method: "select", args: [CATALOG_VARIANT_COLUMNS] });
    expect(builder.calls).toContainEqual({ method: "eq", args: ["phone_model", "iPhone 15"] });
    expect(builder.calls).toContainEqual({ method: "eq", args: ["color", "negro"] });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual(["p1", "p2"]);
    }
  });

  it("returns a failure result when the underlying query errors", async () => {
    const builder = createFakeQueryBuilder({
      data: null,
      error: { message: "boom" },
    });
    const client = createFakeClient({ catalog_variants: builder });

    const result = await scopeProductIdsByVariant(client, { model: "iPhone 15" });

    expect(result).toEqual({ ok: false, reason: "boom" });
  });
});

describe("listCatalogProducts", () => {
  it("queries catalog_products with count:exact and composes in/or/range", async () => {
    const builder = createFakeQueryBuilder({
      data: [{ id: "p1", slug: "a", name: "A", description: null, created_at: "2026-01-01" }],
      error: null,
      count: 1,
    });
    const client = createFakeClient({ catalog_products: builder });

    const result = await listCatalogProducts(client, {
      q: "funda",
      productIds: ["p1", "p2"],
      page: 2,
      limit: 12,
    });

    expect(client.fromCalls).toEqual(["catalog_products"]);
    expect(builder.calls[0]).toEqual({
      method: "select",
      args: [CATALOG_PRODUCT_COLUMNS, { count: "exact" }],
    });
    expect(builder.calls).toContainEqual({ method: "in", args: ["id", ["p1", "p2"]] });
    expect(builder.calls).toContainEqual({
      method: "or",
      args: ["name.ilike.%funda%,description.ilike.%funda%"],
    });
    expect(builder.calls).toContainEqual({ method: "range", args: [12, 23] });
    expect(result).toEqual({
      ok: true,
      data: {
        products: [{ id: "p1", slug: "a", name: "A", description: null, created_at: "2026-01-01" }],
        total: 1,
      },
    });
  });

  it("skips the in() call when productIds is null (no scope filter)", async () => {
    const builder = createFakeQueryBuilder({ data: [], error: null, count: 0 });
    const client = createFakeClient({ catalog_products: builder });

    await listCatalogProducts(client, { q: null, productIds: null, page: 1, limit: 12 });

    expect(builder.calls.some((call) => call.method === "in")).toBe(false);
  });

  it("skips the or() call when q is empty/absent", async () => {
    const builder = createFakeQueryBuilder({ data: [], error: null, count: 0 });
    const client = createFakeClient({ catalog_products: builder });

    await listCatalogProducts(client, { q: null, productIds: null, page: 1, limit: 12 });

    expect(builder.calls.some((call) => call.method === "or")).toBe(false);
  });

  it("returns a well-formed empty result without querying when productIds is an empty array", async () => {
    const client = createFakeClient({});

    const result = await listCatalogProducts(client, {
      q: null,
      productIds: [],
      page: 1,
      limit: 12,
    });

    expect(result).toEqual({ ok: true, data: { products: [], total: 0 } });
    expect(client.fromCalls).toEqual([]);
  });
});

describe("listVariantsForProducts", () => {
  it("queries catalog_variants with the exact column constant, in(), and order(color)", async () => {
    const builder = createFakeQueryBuilder({
      data: [{ id: "v1", product_id: "p1", phone_model: "m", color: "negro", price: 1, in_stock: true }],
      error: null,
    });
    const client = createFakeClient({ catalog_variants: builder });

    const result = await listVariantsForProducts(client, ["p1"]);

    expect(client.fromCalls).toEqual(["catalog_variants"]);
    expect(builder.calls[0]).toEqual({ method: "select", args: [CATALOG_VARIANT_COLUMNS] });
    expect(builder.calls).toContainEqual({ method: "in", args: ["product_id", ["p1"]] });
    expect(builder.calls).toContainEqual({ method: "order", args: ["color"] });
    expect(result.ok).toBe(true);
  });

  it("returns an empty result without querying for an empty productIds list", async () => {
    const client = createFakeClient({});
    const result = await listVariantsForProducts(client, []);
    expect(result).toEqual({ ok: true, data: [] });
    expect(client.fromCalls).toEqual([]);
  });
});

describe("listImagesForProducts", () => {
  it("queries catalog_product_images with the exact column constant, in(), and order(sort_order)", async () => {
    const builder = createFakeQueryBuilder({
      data: [
        {
          id: "i1",
          product_id: "p1",
          variant_id: null,
          storage_path: "a.jpg",
          alt_text: null,
          sort_order: 0,
        },
      ],
      error: null,
    });
    const client = createFakeClient({ catalog_product_images: builder });

    const result = await listImagesForProducts(client, ["p1"]);

    expect(client.fromCalls).toEqual(["catalog_product_images"]);
    expect(builder.calls[0]).toEqual({ method: "select", args: [CATALOG_IMAGE_COLUMNS] });
    expect(builder.calls).toContainEqual({ method: "in", args: ["product_id", ["p1"]] });
    expect(builder.calls).toContainEqual({ method: "order", args: ["sort_order"] });
    expect(result.ok).toBe(true);
  });
});

describe("getCatalogProductBySlug", () => {
  it("queries catalog_products with eq(slug) and maybeSingle()", async () => {
    const builder = createFakeQueryBuilder({
      data: { id: "p1", slug: "fundas-iphone-15", name: "Funda", description: null, created_at: "x" },
      error: null,
    });
    const client = createFakeClient({ catalog_products: builder });

    const result = await getCatalogProductBySlug(client, "fundas-iphone-15");

    expect(client.fromCalls).toEqual(["catalog_products"]);
    expect(builder.calls[0]).toEqual({ method: "select", args: [CATALOG_PRODUCT_COLUMNS] });
    expect(builder.calls).toContainEqual({ method: "eq", args: ["slug", "fundas-iphone-15"] });
    expect(builder.calls.at(-1)).toEqual({ method: "maybeSingle", args: [] });
    expect(result).toEqual({
      ok: true,
      data: { id: "p1", slug: "fundas-iphone-15", name: "Funda", description: null, created_at: "x" },
    });
  });

  it("resolves ok:true with null data when no product matches the slug", async () => {
    const builder = createFakeQueryBuilder({ data: null, error: null });
    const client = createFakeClient({ catalog_products: builder });

    const result = await getCatalogProductBySlug(client, "unknown-slug");

    expect(result).toEqual({ ok: true, data: null });
  });
});

describe("getCatalogFilterOptions", () => {
  it("queries catalog_variants with the exact column constant and dedupes/sorts model+color in memory", async () => {
    const builder = createFakeQueryBuilder({
      data: [
        { id: "v1", product_id: "p1", phone_model: "iPhone 15", color: "negro", price: 1, in_stock: true },
        { id: "v2", product_id: "p1", phone_model: "iPhone 15", color: "transparente", price: 1, in_stock: false },
        { id: "v3", product_id: "p2", phone_model: "Galaxy S24", color: "negro", price: 1, in_stock: false },
      ],
      error: null,
    });
    const client = createFakeClient({ catalog_variants: builder });

    const result = await getCatalogFilterOptions(client);

    expect(client.fromCalls).toEqual(["catalog_variants"]);
    expect(builder.calls[0]).toEqual({ method: "select", args: [CATALOG_VARIANT_COLUMNS] });
    expect(result).toEqual({
      ok: true,
      data: {
        models: ["Galaxy S24", "iPhone 15"],
        colors: ["negro", "transparente"],
      },
    });
  });
});
