import { NextRequest } from "next/server";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * Route Handler tests per design.md's "Route Handler | ... | Import GET
 * directly, call with new NextRequest("http://localhost/api/catalog?…"),
 * vi.mock("@/lib/supabase/server")" testing strategy. `createRequestCatalogClient`
 * is mocked to return an in-memory filtering fake so the REAL `queries.ts`
 * builders run — this proves param parsing, response shaping, status
 * codes, and end-to-end search/filter narrowing without a live Supabase.
 *
 * @see design.md "Route Handler Contract — GET /api/catalog"
 */

type FakeRow = Record<string, unknown>;

function extractIlikeMatches(clause: string, row: FakeRow): boolean {
  // e.g. "name.ilike.%funda%,description.ilike.%funda%"
  return clause.split(",").some((part) => {
    const [column, pattern] = part.split(".ilike.");
    const term = pattern?.replace(/^%/, "").replace(/%$/, "").toLowerCase();
    const value = String(row[column] ?? "").toLowerCase();
    return term !== undefined && value.includes(term);
  });
}

function createFilteringBuilder(rows: FakeRow[], forceError = false) {
  let filtered = [...rows];
  let withCount = false;
  let rangeFrom: number | null = null;
  let rangeTo: number | null = null;

  const builder: Record<string, unknown> = {
    select: (_cols: string, opts?: { count?: string }) => {
      withCount = Boolean(opts?.count);
      return builder;
    },
    eq: (column: string, value: unknown) => {
      filtered = filtered.filter((row) => row[column] === value);
      return builder;
    },
    in: (column: string, values: unknown[]) => {
      filtered = filtered.filter((row) => values.includes(row[column]));
      return builder;
    },
    or: (clause: string) => {
      filtered = filtered.filter((row) => extractIlikeMatches(clause, row));
      return builder;
    },
    order: () => builder,
    range: (from: number, to: number) => {
      rangeFrom = from;
      rangeTo = to;
      return builder;
    },
    maybeSingle: () => {
      if (forceError) {
        return Promise.resolve({ data: null, error: { message: "boom" } });
      }
      return Promise.resolve({ data: filtered[0] ?? null, error: null });
    },
    then: (
      onFulfilled?: (value: unknown) => unknown,
      onRejected?: (reason: unknown) => unknown,
    ) => {
      if (forceError) {
        return Promise.resolve({
          data: null,
          error: { message: "boom" },
          count: null,
        }).then(onFulfilled, onRejected);
      }
      let data = filtered;
      if (rangeFrom !== null && rangeTo !== null) {
        data = data.slice(rangeFrom, rangeTo + 1);
      }
      return Promise.resolve({
        data,
        error: null,
        count: withCount ? filtered.length : null,
      }).then(onFulfilled, onRejected);
    },
  };

  return builder;
}

const PRODUCTS: FakeRow[] = [
  {
    id: "p1",
    slug: "fundas-iphone-15",
    name: "Funda iPhone 15",
    description: "Funda transparente resistente",
    created_at: "2026-01-02",
  },
  {
    id: "p2",
    slug: "fundas-galaxy-s24",
    name: "Funda Galaxy S24",
    description: "Funda negra premium",
    created_at: "2026-01-01",
  },
];

const VARIANTS: FakeRow[] = [
  { id: "v1", product_id: "p1", phone_model: "iPhone 15", color: "negro", price: 5000, in_stock: true },
  { id: "v2", product_id: "p1", phone_model: "iPhone 15", color: "transparente", price: 6000, in_stock: true },
  { id: "v3", product_id: "p2", phone_model: "Galaxy S24", color: "negro", price: 4000, in_stock: false },
];

const IMAGES: FakeRow[] = [
  { id: "i1", product_id: "p1", variant_id: null, storage_path: "fundas-iphone-15/hero.jpg", alt_text: "Funda iPhone 15", sort_order: 0 },
  { id: "i2", product_id: "p2", variant_id: null, storage_path: "fundas-galaxy-s24/hero.jpg", alt_text: "Funda Galaxy S24", sort_order: 0 },
];

interface FakeClientOptions {
  productsError?: boolean;
  variantsError?: boolean;
}

function createFakeSupabaseClient(options: FakeClientOptions = {}) {
  return {
    from: (relation: string) => {
      if (relation === "catalog_products") {
        return createFilteringBuilder(PRODUCTS, options.productsError);
      }
      if (relation === "catalog_variants") {
        return createFilteringBuilder(VARIANTS, options.variantsError);
      }
      if (relation === "catalog_product_images") {
        return createFilteringBuilder(IMAGES);
      }
      throw new Error(`Unexpected relation queried: ${relation}`);
    },
  };
}

vi.mock("@/lib/supabase/server", () => ({
  createRequestCatalogClient: vi.fn(),
}));

vi.mock("@/lib/supabase/env", () => ({
  getCatalogSupabaseEnv: () => ({
    url: "http://127.0.0.1:54321",
    anonKey: "anon-key",
  }),
}));

async function importRouteWithClient(options: FakeClientOptions = {}) {
  const { createRequestCatalogClient } = await import("@/lib/supabase/server");
  vi.mocked(createRequestCatalogClient).mockResolvedValue(
    createFakeSupabaseClient(options) as never,
  );
  const routeModule = await import("./route");
  return routeModule.GET;
}

function requestFor(query: string) {
  return new NextRequest(`http://localhost/api/catalog${query}`);
}

describe("GET /api/catalog", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("returns the first page of all products when no params are supplied", async () => {
    const GET = await importRouteWithClient();

    const response = await GET(requestFor(""));
    expect(response.status).toBe(200);

    const body = await response.json();
    expect(body.items).toHaveLength(2);
    expect(body.page).toBe(1);
    expect(body.limit).toBe(12);
    expect(body.total).toBe(2);
    expect(body.totalPages).toBe(1);
  });

  it("narrows to only products matching combined q + model + color + page", async () => {
    const GET = await importRouteWithClient();

    const response = await GET(
      requestFor("?q=funda&model=iPhone+15&color=negro&page=1"),
    );
    expect(response.status).toBe(200);

    const body = await response.json();
    expect(body.items).toHaveLength(1);
    expect(body.items[0].slug).toBe("fundas-iphone-15");
    expect(body.applied).toEqual({ q: "funda", model: "iPhone 15", color: "negro" });
  });

  it("returns a well-formed empty result for a model that matches nothing", async () => {
    const GET = await importRouteWithClient();

    const response = await GET(requestFor("?model=Nonexistent+Model"));
    expect(response.status).toBe(200);

    const body = await response.json();
    expect(body.items).toEqual([]);
    expect(body.total).toBe(0);
  });

  it.each([
    ["page", "0"],
    ["page", "-1"],
    ["page", "abc"],
  ])("rejects %s=%s with 400 invalid_query", async (param, value) => {
    const GET = await importRouteWithClient();

    const response = await GET(requestFor(`?${param}=${value}`));
    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.error).toBe("invalid_query");
  });

  it("rejects limit=999 with 400 invalid_query", async () => {
    const GET = await importRouteWithClient();

    const response = await GET(requestFor("?limit=999"));
    expect(response.status).toBe(400);
    const body = await response.json();
    expect(body.error).toBe("invalid_query");
  });

  it("sanitizes PostgREST metacharacters in q instead of erroring", async () => {
    const GET = await importRouteWithClient();

    const response = await GET(requestFor("?q=" + encodeURIComponent("a,b(c)")));
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.applied.q).toBe("abc");
  });

  it("truncates a q longer than 80 characters instead of erroring", async () => {
    const GET = await importRouteWithClient();
    const longQ = "a".repeat(200);

    const response = await GET(requestFor(`?q=${longQ}`));
    expect(response.status).toBe(200);
    const body = await response.json();
    expect(body.applied.q).toHaveLength(80);
  });

  it("returns 503 catalog_unavailable on upstream Supabase failure, never 500", async () => {
    const GET = await importRouteWithClient({ productsError: true });

    const response = await GET(requestFor(""));
    expect(response.status).toBe(503);
    const body = await response.json();
    expect(body.error).toBe("catalog_unavailable");
  });

  it("never includes a cost or quantity key in a successful response, including empty results", async () => {
    const GET = await importRouteWithClient();

    const emptyResponse = await GET(requestFor("?model=Nonexistent+Model"));
    const emptyBody = await emptyResponse.json();
    expect(JSON.stringify(emptyBody).toLowerCase()).not.toMatch(/cost|quantity/);

    const fullResponse = await GET(requestFor(""));
    const fullBody = await fullResponse.json();
    expect(JSON.stringify(fullBody).toLowerCase()).not.toMatch(/cost|quantity/);
  });

  it("sets a stale-while-revalidate Cache-Control header on success", async () => {
    const GET = await importRouteWithClient();

    const response = await GET(requestFor(""));
    expect(response.headers.get("Cache-Control")).toBe(
      "public, max-age=0, s-maxage=300, stale-while-revalidate=600",
    );
  });
});
