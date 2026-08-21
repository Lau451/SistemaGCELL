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
import { MessageCircle } from "lucide-react";
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
import { IconButton } from "@/components/ui/icon-button";
import {
  VariantPicker,
  type VariantPickerVariant,
} from "@/components/catalog/variant-picker";

export const revalidate = 300;

const GCELL_WHATSAPP_NUMBER = "5493471611216";
const GCELL_INSTAGRAM_URL = "https://www.instagram.com/gcell_phones";

function InstagramIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
      <path d="M16 11.37a4 4 0 1 1-7.914 1.174 4 4 0 0 1 7.914-1.174z" />
      <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
    </svg>
  );
}

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
    <article className="mx-auto max-w-5xl px-4 py-8 sm:py-10">
      <div className="grid grid-cols-1 gap-8 md:grid-cols-2 md:gap-10">
        <VariantPicker variants={variants} fallbackImage={fallbackImage} />
        <div className="flex flex-col gap-4">
          <h1 className="font-heading text-2xl font-bold text-foreground sm:text-3xl">
            {product.name}
          </h1>
          {product.description && (
            <p className="text-muted-foreground text-sm leading-relaxed sm:text-base">
              {product.description}
            </p>
          )}
          <div className="mt-2 flex items-center gap-4">
            <IconButton
              variant="filled"
              aria-label={`Consultar por ${product.name} en WhatsApp`}
              render={
                <a
                  href={`https://wa.me/${GCELL_WHATSAPP_NUMBER}?text=${encodeURIComponent(
                    `Hola! Quería consultar por ${product.name}`,
                  )}`}
                  target="_blank"
                  rel="noopener noreferrer"
                />
              }
            >
              <MessageCircle />
            </IconButton>
            <IconButton
              variant="outline"
              aria-label={`Consultar por ${product.name} en Instagram`}
              render={
                <a
                  href={GCELL_INSTAGRAM_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                />
              }
            >
              <InstagramIcon />
            </IconButton>
          </div>
        </div>
      </div>
    </article>
  );
}
