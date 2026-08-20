/**
 * `GET /api/catalog` — search/filter/pagination Route Handler backing the
 * client-side catalog search. Uses `createRequestCatalogClient()` (the
 * request-bound factory from PR1) and the same query builders `queries.ts`
 * (PR2) already exposes — this route adds zero new Supabase query shapes,
 * only param parsing + response shaping around the existing builders.
 *
 * Reads never throw: every builder returns `{ ok: true, data } | { ok:
 * false, reason }`, so an upstream Supabase failure becomes a `503` here,
 * never an unhandled `500`.
 *
 * @see design.md "Route Handler Contract — GET /api/catalog"
 */
import { NextResponse, type NextRequest } from "next/server";
import { deriveListingCard } from "@/lib/catalog/derive";
import {
  getCatalogFilterOptions,
  listCatalogProducts,
  listImagesForProducts,
  listVariantsForProducts,
  scopeProductIdsByVariant,
} from "@/lib/catalog/queries";
import {
  MAX_SEARCH_TERM_LENGTH,
  parseLimitParam,
  parsePageParam,
  sanitizeSearchTerm,
} from "@/lib/catalog/query-params";
import { toPublicPhotoUrl } from "@/lib/catalog/storage-url";
import { getCatalogSupabaseEnv } from "@/lib/supabase/env";
import { createRequestCatalogClient } from "@/lib/supabase/server";

const SUCCESS_CACHE_CONTROL =
  "public, max-age=0, s-maxage=300, stale-while-revalidate=600";

export interface CatalogListItem {
  id: string;
  slug: string;
  name: string;
  shortDescription: string | null;
  priceFrom: number;
  hasPriceRange: boolean;
  inStock: boolean;
  colors: string[];
  heroImageUrl: string | null;
  heroImageAlt: string | null;
}

export interface CatalogListResponse {
  items: CatalogListItem[];
  page: number;
  limit: number;
  total: number;
  totalPages: number;
  filters: { models: string[]; colors: string[] };
  applied: { q: string | null; model: string | null; color: string | null };
}

function invalidQuery(reason: string) {
  return NextResponse.json(
    { error: "invalid_query", details: reason },
    { status: 400 },
  );
}

function catalogUnavailable() {
  return NextResponse.json({ error: "catalog_unavailable" }, { status: 503 });
}

/** Same length bound as `q` — an exact-match filter value has no reason to exceed it. */
function readBoundedParam(raw: string | null): string | null {
  const trimmed = raw?.trim().slice(0, MAX_SEARCH_TERM_LENGTH);
  return trimmed ? trimmed : null;
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;

  const pageResult = parsePageParam(searchParams.get("page"));
  if (!pageResult.ok) {
    return invalidQuery(pageResult.reason);
  }

  const limitResult = parseLimitParam(searchParams.get("limit"));
  if (!limitResult.ok) {
    return invalidQuery(limitResult.reason);
  }

  const rawQ = searchParams.get("q");
  const q = rawQ !== null ? sanitizeSearchTerm(rawQ) || null : null;
  const model = readBoundedParam(searchParams.get("model"));
  const color = readBoundedParam(searchParams.get("color"));

  const client = await createRequestCatalogClient();
  const { url: supabaseUrl } = getCatalogSupabaseEnv();

  const scopeResult = await scopeProductIdsByVariant(client, { model, color });
  if (!scopeResult.ok) {
    return catalogUnavailable();
  }

  const listingResult = await listCatalogProducts(client, {
    q,
    productIds: scopeResult.data,
    page: pageResult.value,
    limit: limitResult.value,
  });
  if (!listingResult.ok) {
    return catalogUnavailable();
  }

  const filterOptionsResult = await getCatalogFilterOptions(client);
  if (!filterOptionsResult.ok) {
    return catalogUnavailable();
  }

  const { products, total } = listingResult.data;
  const productIds = products.map((product) => product.id);

  const [variantsResult, imagesResult] = await Promise.all([
    listVariantsForProducts(client, productIds),
    listImagesForProducts(client, productIds),
  ]);
  if (!variantsResult.ok || !imagesResult.ok) {
    return catalogUnavailable();
  }

  const variants = variantsResult.data;
  const images = imagesResult.data;

  const items: CatalogListItem[] = products.map((product) => {
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
      id: card.id,
      slug: card.slug,
      name: card.name,
      shortDescription: card.shortDescription,
      priceFrom: card.priceFrom,
      hasPriceRange: card.hasPriceRange,
      inStock: card.inStock,
      colors: card.colors,
      heroImageUrl: card.heroImage
        ? toPublicPhotoUrl(supabaseUrl, card.heroImage.storage_path)
        : null,
      heroImageAlt: card.heroImage?.alt_text ?? null,
    };
  });

  const body: CatalogListResponse = {
    items,
    page: pageResult.value,
    limit: limitResult.value,
    total,
    totalPages: Math.max(1, Math.ceil(total / limitResult.value)),
    filters: filterOptionsResult.data,
    applied: { q, model, color },
  };

  return NextResponse.json(body, {
    status: 200,
    headers: { "Cache-Control": SUCCESS_CACHE_CONTROL },
  });
}
