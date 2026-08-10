/**
 * `/product/[slug]` — product detail with the interactive color/variant
 * picker. Classic ISR (`revalidate = 300`). No `generateStaticParams`:
 * `dynamicParams` defaults to `true`, so a new product's page renders
 * on-demand at first request instead of requiring a reachable Supabase at
 * build time (design.md "Decision: No generateStaticParams; reads never
 * throw").
 *
 * All variants + all images for the product are fetched once here and
 * serialized into `VariantPicker` as plain props — the client component
 * makes zero additional fetches when swapping color.
 */
import { notFound } from "next/navigation";
import { deriveHeroImage } from "@/lib/catalog/derive";
import {
  getCatalogProductBySlug,
  listImagesForProducts,
  listVariantsForProducts,
} from "@/lib/catalog/queries";
import { toPublicPhotoUrl } from "@/lib/catalog/storage-url";
import { getCatalogSupabaseEnv } from "@/lib/supabase/env";
import { createAnonCatalogClient } from "@/lib/supabase/server";
import { CatalogEmptyState } from "@/components/catalog/catalog-empty-state";
import {
  VariantPicker,
  type VariantPickerVariant,
} from "@/components/catalog/variant-picker";

export const revalidate = 300;

interface ProductDetailPageProps {
  params: Promise<{ slug: string }>;
}

export default async function ProductDetailPage({
  params,
}: ProductDetailPageProps) {
  const { slug } = await params;
  const client = createAnonCatalogClient();
  const { url: supabaseUrl } = getCatalogSupabaseEnv();

  const productResult = await getCatalogProductBySlug(client, slug);
  if (!productResult.ok) {
    return <CatalogEmptyState variant="error" />;
  }

  const product = productResult.data;
  if (!product) {
    notFound();
  }

  const [variantsResult, imagesResult] = await Promise.all([
    listVariantsForProducts(client, [product.id]),
    listImagesForProducts(client, [product.id]),
  ]);

  if (!variantsResult.ok || !imagesResult.ok) {
    return <CatalogEmptyState variant="error" />;
  }

  const variantRows = variantsResult.data;
  const imageRows = imagesResult.data;

  const variants: VariantPickerVariant[] = variantRows.map((variant) => ({
    id: variant.id,
    color: variant.color,
    price: variant.price,
    inStock: variant.in_stock,
    images: imageRows
      .filter((image) => image.variant_id === variant.id)
      .sort((a, b) => a.sort_order - b.sort_order)
      .map((image) => ({
        url: toPublicPhotoUrl(supabaseUrl, image.storage_path),
        alt: image.alt_text ?? product.name,
      })),
  }));

  const heroImage = deriveHeroImage(variantRows, imageRows);
  const fallbackImage = heroImage
    ? {
        url: toPublicPhotoUrl(supabaseUrl, heroImage.storage_path),
        alt: heroImage.alt_text ?? product.name,
      }
    : null;

  return (
    <article className="mx-auto flex max-w-4xl flex-col gap-6 px-4 py-10">
      <div>
        <h1 className="text-2xl font-semibold">{product.name}</h1>
        {product.description && (
          <p className="text-muted-foreground mt-2">{product.description}</p>
        )}
      </div>
      <VariantPicker variants={variants} fallbackImage={fallbackImage} />
    </article>
  );
}
