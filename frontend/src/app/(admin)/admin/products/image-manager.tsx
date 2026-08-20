"use client";

/**
 * `ImageManager` — client component rendered on the product detail page
 * (`[id]/page.tsx`), the ONLY UI surface for `uploadProductImageAction` /
 * `deleteProductImageAction` / `reorderProductImagesAction` (design.md's
 * "Frontend relay" — Server Actions are the sole write path).
 *
 * State-sync strategy: `initialImages` IS the rendered list — there is no
 * local `useState` copy of it. After ANY successful mutation (upload/
 * delete/reorder) this calls `router.refresh()` rather than optimistically
 * splicing the mutated image in client-side. The Server Actions already
 * call `revalidatePath` on the product detail route, so a refresh re-runs
 * `[id]/page.tsx`'s server fetch and delivers the authoritative list back
 * down through this same `initialImages` prop on the next render. Local
 * `useTransition` state (`isMutating`) exists only to disable buttons
 * while a mutation is in flight — never as a second source of truth for
 * the list itself.
 *
 * Reorder is whole-list (design.md Decision 6: "full ordered id list"),
 * driven by keyboard-accessible Up/Down buttons rather than drag-and-drop
 * — no new dependency, no pointer-event test complexity.
 *
 * Thumbnails resolve `storage_path` through the SAME public-URL builder
 * the public catalog already uses (`toPublicPhotoUrl` +
 * `getCatalogSupabaseEnv`, both read-only/pure) — no bespoke bucket URL
 * scheme invented here.
 *
 * @see design.md "Data Flow", "Decision 6: Reorder", "Decision 8"
 */
import { useActionState, useEffect, useMemo, useRef, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { toPublicPhotoUrl } from "@/lib/catalog/storage-url";
import { getCatalogSupabaseEnv } from "@/lib/supabase/env";
import {
  deleteProductImageAction,
  reorderProductImagesAction,
  updateProductImageAltTextAction,
  uploadProductImageAction,
  type ProductFormState,
} from "./actions";

export interface AdminProductImage {
  id: string;
  product_id: string;
  variant_id: string | null;
  storage_path: string;
  alt_text: string | null;
  sort_order: number;
}

export interface ImageManagerVariant {
  id: string;
  color: string;
}

export interface ImageManagerProps {
  productId: string;
  variants: ImageManagerVariant[];
  initialImages: AdminProductImage[];
}

const INITIAL_STATE: ProductFormState = { error: null };

function assignmentLabel(
  image: AdminProductImage,
  variants: ImageManagerVariant[],
): string {
  if (image.variant_id === null) {
    return "Hero";
  }
  return (
    variants.find((variant) => variant.id === image.variant_id)?.color ??
    "Unknown variant"
  );
}

export function ImageManager({
  productId,
  variants,
  initialImages,
}: ImageManagerProps) {
  const router = useRouter();
  const [isMutating, startMutating] = useTransition();
  const formRef = useRef<HTMLFormElement>(null);
  const altTextRefs = useRef<Record<string, HTMLInputElement | null>>({});
  const [altTextErrors, setAltTextErrors] = useState<Record<string, string>>(
    {},
  );
  // `images` intentionally has NO local `useState`: `initialImages` is the
  // single source of truth (server-fetched, revalidated via `revalidatePath`
  // inside every Server Action), and `router.refresh()` after each mutation
  // re-runs `[id]/page.tsx`'s server fetch and delivers the updated list
  // straight back down through this prop.
  const images = initialImages;
  const boundUploadAction = useMemo(
    () => uploadProductImageAction.bind(null, productId),
    [productId],
  );
  const [uploadState, uploadAction, uploadPending] = useActionState(
    boundUploadAction,
    INITIAL_STATE,
  );

  useEffect(() => {
    // `state !== INITIAL_STATE` distinguishes "never submitted yet" (the
    // very first render, where `useActionState` hands back the exact
    // `INITIAL_STATE` reference) from "just submitted and succeeded" (a
    // freshly-returned `{ error: null }` object with a different
    // identity) — without this check, a bare `state.error === null`
    // would also be true on mount and refresh on every render.
    if (uploadState !== INITIAL_STATE && uploadState.error === null) {
      formRef.current?.reset();
      router.refresh();
    }
  }, [uploadState, router]);

  function handleDelete(imageId: string) {
    const formData = new FormData();
    formData.set("product-id", productId);
    formData.set("image-id", imageId);

    startMutating(async () => {
      await deleteProductImageAction(formData);
      router.refresh();
    });
  }

  function handleSaveAltText(imageId: string) {
    const altText = altTextRefs.current[imageId]?.value ?? "";
    const formData = new FormData();
    formData.set("product-id", productId);
    formData.set("image-id", imageId);
    formData.set("alt-text", altText);

    startMutating(async () => {
      const result = await updateProductImageAltTextAction(formData);
      if (result.error) {
        setAltTextErrors((previous) => ({
          ...previous,
          [imageId]: result.error as string,
        }));
        return;
      }
      setAltTextErrors((previous) =>
        Object.fromEntries(
          Object.entries(previous).filter(([id]) => id !== imageId),
        ),
      );
      router.refresh();
    });
  }

  function moveImage(index: number, direction: -1 | 1) {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= images.length) {
      return;
    }

    const reordered = [...images];
    const [moved] = reordered.splice(index, 1);
    reordered.splice(targetIndex, 0, moved);
    const orderedIds = reordered.map((image) => image.id);

    startMutating(async () => {
      await reorderProductImagesAction(productId, orderedIds);
      router.refresh();
    });
  }

  const { url: supabaseUrl } = getCatalogSupabaseEnv();

  return (
    <div className="flex flex-col gap-6">
      <h2 className="text-xl font-semibold">Images</h2>

      <form
        ref={formRef}
        action={uploadAction}
        className="border-border flex flex-col gap-3 border-b pb-4"
      >
        <div className="flex flex-col gap-1.5">
          <label htmlFor="image-file" className="text-sm font-medium">
            Image file
          </label>
          <input
            id="image-file"
            name="file"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            className="text-sm"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="image-variant" className="text-sm font-medium">
            Assign to
          </label>
          <select
            id="image-variant"
            name="variant-id"
            defaultValue=""
            className="border-border rounded-md border px-3 py-2 text-sm"
          >
            <option value="">Hero (no variant)</option>
            {variants.map((variant) => (
              <option key={variant.id} value={variant.id}>
                {variant.color}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="image-alt-text" className="text-sm font-medium">
            Alt text (optional)
          </label>
          <input
            id="image-alt-text"
            name="alt-text"
            type="text"
            className="border-border rounded-md border px-3 py-2 text-sm"
          />
        </div>

        {uploadState.error && (
          <p role="alert" className="text-destructive text-sm">
            {uploadState.error}
          </p>
        )}

        <Button type="submit" disabled={uploadPending}>
          Upload image
        </Button>
      </form>

      <div className="flex flex-col gap-3">
        {images.length === 0 && (
          <p className="text-muted-foreground text-sm">No images yet.</p>
        )}
        {images.map((image, index) => (
          <div
            key={image.id}
            className="border-border flex flex-wrap items-center gap-3 border-b pb-3"
          >
            {/* Plain `<img>`, not `next/image` — the bucket host isn't in
                `next.config`'s `remotePatterns` and adding it is out of
                scope for this change. */}
            <img
              src={toPublicPhotoUrl(supabaseUrl, image.storage_path)}
              alt={image.alt_text ?? ""}
              className="border-border h-16 w-16 rounded-md border object-cover"
            />
            <div className="flex flex-col gap-0.5 text-sm">
              <span className="font-medium">
                {assignmentLabel(image, variants)}
              </span>
              <span className="text-muted-foreground text-xs">
                {image.storage_path}
              </span>
            </div>
            <div className="flex flex-col gap-1.5">
              <label
                htmlFor={`alt-text-${image.id}`}
                className="text-sm font-medium"
              >
                Alt text
              </label>
              <input
                id={`alt-text-${image.id}`}
                type="text"
                defaultValue={image.alt_text ?? ""}
                ref={(el) => {
                  altTextRefs.current[image.id] = el;
                }}
                className="border-border rounded-md border px-2 py-1 text-sm"
              />
              {altTextErrors[image.id] && (
                <p role="alert" className="text-destructive text-sm">
                  {altTextErrors[image.id]}
                </p>
              )}
              <Button
                type="button"
                variant="outline"
                disabled={isMutating}
                onClick={() => handleSaveAltText(image.id)}
              >
                Save alt text
              </Button>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                disabled={index === 0 || isMutating}
                onClick={() => moveImage(index, -1)}
              >
                Up
              </Button>
              <Button
                type="button"
                variant="outline"
                disabled={index === images.length - 1 || isMutating}
                onClick={() => moveImage(index, 1)}
              >
                Down
              </Button>
              <Button
                type="button"
                variant="secondary"
                disabled={isMutating}
                onClick={() => handleDelete(image.id)}
              >
                Delete
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
