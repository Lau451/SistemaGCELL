"use server";

/**
 * Write Server Actions for `/admin/products` — the ONLY write surface for
 * this change, per design.md's "Decision: no write Route Handlers —
 * Server Actions relay directly": a cookie-authenticated JSON Route
 * Handler is a CSRF surface (`request.json()` ignores `Content-Type`),
 * whereas Next's Server Actions enforce origin matching natively. All
 * four actions here relay through the same `adminBackendFetch` the read
 * Route Handlers use.
 *
 * **Money precision** (design.md's threat matrix, item 5): variant
 * `price`/`cost` `FormData` values are relayed to `adminBackendFetch` as
 * the exact string the browser submitted — NEVER `parseFloat`/`Number()`
 * anywhere in this file. `FormData` yields a string; `adminBackendFetch`
 * JSON-stringifies it verbatim; FastAPI's Pydantic parses that string
 * straight into `Decimal`. A single numeric coercion here would
 * reintroduce exactly the precision loss `_validate_money` exists to
 * prevent.
 *
 * Variant rows are submitted as parallel repeated fields (`variant-id`,
 * `variant-color`, `variant-price`, `variant-cost`), zipped positionally
 * via `formData.getAll()` — `product-form.tsx` renders one of each per
 * row, in the same order, so `getAll()`'s order matches across fields. A
 * blank `variant-id` means "new variant" (no `id` sent, matching the
 * backend's `AdminVariantInput.id: UUID | None = None`).
 *
 * @see design.md "Frontend relay", "Decision: `PATCH` never retires"
 */
import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import { extractAdminError } from "@/lib/admin/api-error";
import { adminBackendFetch } from "@/lib/admin/backend-fetch";
import {
  signedQuantityDelta,
  type MovementDirection,
} from "./stock-movement-sign";

const ADMIN_LOGIN_PATH = "/admin/login";
const ADMIN_PRODUCTS_PATH = "/admin/products";
const BACKEND_UNAVAILABLE_MESSAGE =
  "No pudimos conectar con el servidor. Intentá nuevamente.";

export interface ProductFormState {
  error: string | null;
}

// Images render on the product detail page (`[id]/page.tsx`), not the
// list page — revalidating `ADMIN_PRODUCTS_PATH` alone would leave a
// stale gallery after an upload/delete/reorder.
function adminProductDetailPath(productId: string): string {
  return `${ADMIN_PRODUCTS_PATH}/${productId}`;
}

interface VariantWritePayload {
  id?: string;
  color: string;
  price: string;
  cost: string;
  initial_quantity?: string;
}

interface ProductWritePayload {
  name: string;
  model: string;
  description?: string;
  short_description?: string;
  variants: VariantWritePayload[];
}

/**
 * `description`/`short_description` follow the same omit-if-blank
 * convention as `reason`/`initial_quantity` above — a blank field is
 * dropped from the payload entirely rather than sent as `""`, which is
 * what makes `AdminProductWriteRequest`'s `Field(default=None)` persist
 * `null` (spec: "Product is creatable with both fields blank"). Because
 * the form always re-renders and resubmits BOTH fields' current values
 * (`product-form.tsx`'s `defaultValue`), an edit to only one field still
 * relays the other's unchanged, non-blank value here — never omitted,
 * never accidentally cleared (spec: "Editing updates both fields
 * independently"). An admin who deliberately blanks a previously-set
 * field on the form DOES clear it this way — the same full-replacement
 * semantics `name`/`model` already have, documented in design.md's Open
 * Questions.
 */
function optionalTrimmedField(
  formData: FormData,
  key: string,
): string | undefined {
  const raw = formData.get(key);
  return typeof raw === "string" && raw.trim() !== "" ? raw : undefined;
}

function buildVariantsPayload(formData: FormData): VariantWritePayload[] {
  const ids = formData.getAll("variant-id");
  const colors = formData.getAll("variant-color");
  const prices = formData.getAll("variant-price");
  const costs = formData.getAll("variant-cost");
  // Rendered ONLY on the create form's rows (design.md Decision 4) — on the
  // edit form this array is empty, so `initialQuantities[index]` is always
  // `undefined` there and the key is never added, matching the backend's
  // PATCH-ignores-the-field contract.
  const initialQuantities = formData.getAll("variant-initial-quantity");

  const variants: VariantWritePayload[] = [];
  for (let index = 0; index < colors.length; index += 1) {
    const rawId = ids[index];
    const id =
      typeof rawId === "string" && rawId.trim() !== "" ? rawId : undefined;
    const rawInitialQuantity = initialQuantities[index];
    const initialQuantity =
      typeof rawInitialQuantity === "string" && rawInitialQuantity.trim() !== ""
        ? rawInitialQuantity
        : undefined;

    variants.push({
      ...(id !== undefined ? { id } : {}),
      color: String(colors[index] ?? ""),
      // Verbatim strings — see the file-level money-precision note.
      // `initial_quantity` follows the SAME convention: never
      // `Number()`/`parseInt()` here, relayed exactly as submitted.
      price: String(prices[index] ?? ""),
      cost: String(costs[index] ?? ""),
      ...(initialQuantity !== undefined ? { initial_quantity: initialQuantity } : {}),
    });
  }
  return variants;
}

function buildProductPayload(formData: FormData): ProductWritePayload {
  const description = optionalTrimmedField(formData, "description");
  const shortDescription = optionalTrimmedField(formData, "short_description");

  return {
    name: String(formData.get("name") ?? ""),
    model: String(formData.get("model") ?? ""),
    ...(description !== undefined ? { description } : {}),
    ...(shortDescription !== undefined
      ? { short_description: shortDescription }
      : {}),
    variants: buildVariantsPayload(formData),
  };
}

async function submitProduct(
  path: string,
  method: "POST" | "PATCH",
  formData: FormData,
): Promise<ProductFormState> {
  const body = buildProductPayload(formData);
  const result = await adminBackendFetch(path, { method, body });

  if (result.outcome === "unauthenticated") {
    redirect(ADMIN_LOGIN_PATH);
  }

  if (result.outcome === "backend_unavailable") {
    return { error: BACKEND_UNAVAILABLE_MESSAGE };
  }

  if (result.status === 201 || result.status === 200) {
    revalidatePath(ADMIN_PRODUCTS_PATH);
    redirect(ADMIN_PRODUCTS_PATH);
  }

  return { error: extractAdminError(result.status, result.body) };
}

export async function createProductAction(
  _prevState: ProductFormState,
  formData: FormData,
): Promise<ProductFormState> {
  return submitProduct("/admin/products", "POST", formData);
}

export async function updateProductAction(
  productId: string,
  _prevState: ProductFormState,
  formData: FormData,
): Promise<ProductFormState> {
  return submitProduct(`/admin/products/${productId}`, "PATCH", formData);
}

export async function retireProductAction(formData: FormData): Promise<void> {
  const productId = String(formData.get("product-id") ?? "");
  const result = await adminBackendFetch(`/admin/products/${productId}`, {
    method: "DELETE",
  });

  if (result.outcome === "unauthenticated") {
    redirect(ADMIN_LOGIN_PATH);
  }

  revalidatePath(ADMIN_PRODUCTS_PATH);
}

/**
 * Upload a product image — the multipart write path from design.md's
 * Data Flow diagram. The incoming `file` (a `File`, never buffered
 * through `.arrayBuffer()`/`.text()`) is relayed straight into a new
 * `FormData` passed as `adminBackendFetch`'s `body`, which — per Decision
 * 8 — forwards `FormData` to `fetch` untouched with no `Content-Type`
 * header, letting the browser set the multipart boundary.
 *
 * Optional `variant-id`/`alt-text` incoming fields (kebab-case, matching
 * this file's other form-field conventions) are relayed as the backend's
 * `variant_id`/`alt_text` `Form(...)` fields.
 */
export async function uploadProductImageAction(
  productId: string,
  _prevState: ProductFormState,
  formData: FormData,
): Promise<ProductFormState> {
  const file = formData.get("file");
  const relay = new FormData();
  if (file instanceof File) {
    relay.set("file", file);
  }

  const variantId = formData.get("variant-id");
  if (typeof variantId === "string" && variantId.trim() !== "") {
    relay.set("variant_id", variantId);
  }

  const altText = formData.get("alt-text");
  if (typeof altText === "string" && altText.trim() !== "") {
    relay.set("alt_text", altText);
  }

  const result = await adminBackendFetch(
    `/admin/products/${productId}/images`,
    { method: "POST", body: relay },
  );

  if (result.outcome === "unauthenticated") {
    redirect(ADMIN_LOGIN_PATH);
  }

  if (result.outcome === "backend_unavailable") {
    return { error: BACKEND_UNAVAILABLE_MESSAGE };
  }

  if (result.status === 201) {
    revalidatePath(adminProductDetailPath(productId));
    return { error: null };
  }

  return { error: extractAdminError(result.status, result.body) };
}

/**
 * Delete a product image — same fire-and-forget pattern as
 * `retireVariantAction`: no error state, just gate + relay + revalidate.
 */
export async function deleteProductImageAction(
  formData: FormData,
): Promise<void> {
  const productId = String(formData.get("product-id") ?? "");
  const imageId = String(formData.get("image-id") ?? "");
  const result = await adminBackendFetch(
    `/admin/products/${productId}/images/${imageId}`,
    { method: "DELETE" },
  );

  if (result.outcome === "unauthenticated") {
    redirect(ADMIN_LOGIN_PATH);
  }

  revalidatePath(adminProductDetailPath(productId));
}

/**
 * Update an image's alt text — DD3's dedicated `PATCH .../images/{id}`
 * route, independent of re-uploading the file. `alt_text` is a REQUIRED
 * key on the backend's write model (`str | None`, no default) — a blank
 * submitted value is relayed as an explicit `null` to clear the column
 * (design.md DD3: "an explicit null/blank-after-strip clears the column
 * — the only way to undo bad alt text"), never omitted. Same
 * FormData-via-manual-construction + fire pattern as
 * `deleteProductImageAction`, but returns a `ProductFormState` (like
 * `reorderProductImagesAction`) so `image-manager.tsx` can surface a
 * failed save (e.g. a stale/cross-parent image id) via `role=alert`.
 */
export async function updateProductImageAltTextAction(
  formData: FormData,
): Promise<ProductFormState> {
  const productId = String(formData.get("product-id") ?? "");
  const imageId = String(formData.get("image-id") ?? "");
  const raw = formData.get("alt-text");
  const altText = typeof raw === "string" && raw.trim() !== "" ? raw : null;

  const result = await adminBackendFetch(
    `/admin/products/${productId}/images/${imageId}`,
    { method: "PATCH", body: { alt_text: altText } },
  );

  if (result.outcome === "unauthenticated") {
    redirect(ADMIN_LOGIN_PATH);
  }

  if (result.outcome === "backend_unavailable") {
    return { error: BACKEND_UNAVAILABLE_MESSAGE };
  }

  if (result.status === 200) {
    revalidatePath(adminProductDetailPath(productId));
    return { error: null };
  }

  return { error: extractAdminError(result.status, result.body) };
}

/**
 * Generate a draft product-copy pair (content-ai-domains PR 11) —
 * `POST .../copy/generate`, DD5's D5 draft-only contract: this action
 * NEVER submits `updateProductAction`/`createProductAction` itself, and
 * the backend route it calls has zero write side effect either way. The
 * caller (`product-form.tsx`) is responsible for prefilling the two form
 * fields from the returned draft and leaving the existing "Save changes"
 * button as the only write path. No request body — the route acts on
 * exactly the one `productId` in the URL (spec "No bulk generate route
 * exists").
 */
export interface GenerateCopyResult {
  short_description: string | null;
  description: string | null;
  error: string | null;
}

export async function generateProductCopyAction(
  productId: string,
): Promise<GenerateCopyResult> {
  const result = await adminBackendFetch(
    `/admin/products/${productId}/copy/generate`,
    { method: "POST" },
  );

  if (result.outcome === "unauthenticated") {
    redirect(ADMIN_LOGIN_PATH);
  }

  if (result.outcome === "backend_unavailable") {
    return {
      short_description: null,
      description: null,
      error: BACKEND_UNAVAILABLE_MESSAGE,
    };
  }

  if (result.status === 200) {
    const body = result.body as {
      short_description: string | null;
      description: string | null;
    };
    return {
      short_description: body.short_description,
      description: body.description,
      error: null,
    };
  }

  return {
    short_description: null,
    description: null,
    error: extractAdminError(result.status, result.body),
  };
}

/**
 * Generate a draft alt-text string for one product photo (content-ai-domains
 * PR 11) — `POST .../images/{image_id}/alt-text/generate`. Same draft-only
 * contract as `generateProductCopyAction`: the caller (`image-manager.tsx`)
 * prefills the alt-text input; the existing `updateProductImageAltTextAction`
 * PATCH remains the only write path.
 */
export interface GenerateAltTextResult {
  alt_text: string | null;
  error: string | null;
}

export async function generateImageAltTextAction(
  productId: string,
  imageId: string,
): Promise<GenerateAltTextResult> {
  const result = await adminBackendFetch(
    `/admin/products/${productId}/images/${imageId}/alt-text/generate`,
    { method: "POST" },
  );

  if (result.outcome === "unauthenticated") {
    redirect(ADMIN_LOGIN_PATH);
  }

  if (result.outcome === "backend_unavailable") {
    return { alt_text: null, error: BACKEND_UNAVAILABLE_MESSAGE };
  }

  if (result.status === 200) {
    const body = result.body as { alt_text: string };
    return { alt_text: body.alt_text, error: null };
  }

  return { alt_text: null, error: extractAdminError(result.status, result.body) };
}

/**
 * Reorder a product's images — design.md Decision 6: the full ordered id
 * list, not deltas. Called directly from the (Phase 7) drag-reorder UI
 * rather than bound to a `<form>` submit, so it takes plain arguments
 * instead of `(prevState, formData)`.
 */
export async function reorderProductImagesAction(
  productId: string,
  imageIds: string[],
): Promise<ProductFormState> {
  const result = await adminBackendFetch(
    `/admin/products/${productId}/images/order`,
    { method: "PUT", body: { image_ids: imageIds } },
  );

  if (result.outcome === "unauthenticated") {
    redirect(ADMIN_LOGIN_PATH);
  }

  if (result.outcome === "backend_unavailable") {
    return { error: BACKEND_UNAVAILABLE_MESSAGE };
  }

  if (result.status === 200) {
    revalidatePath(adminProductDetailPath(productId));
    return { error: null };
  }

  return { error: extractAdminError(result.status, result.body) };
}

/**
 * Record a stock movement for a single variant — `stock-manager.tsx`'s
 * single record form. Builds the variant-scoped path and derives
 * `quantity_delta`'s sign via `signedQuantityDelta` client-side (Decision
 * 7) before relaying JSON to `RecordVariantStockMovementUseCase` (already
 * live from PR1). `reason` is optional for every movement type (spec:
 * "Reason Is Optional On Every Movement Type") and is omitted from the
 * body entirely when blank, rather than sent as an empty string.
 */
export async function recordStockMovementAction(
  productId: string,
  _prevState: ProductFormState,
  formData: FormData,
): Promise<ProductFormState> {
  const variantId = String(formData.get("variant-id") ?? "");
  const movementType = String(formData.get("movement-type") ?? "");
  const magnitude = Number(formData.get("magnitude") ?? 0);
  const direction = (
    formData.get("direction") === "decrease" ? "decrease" : "increase"
  ) satisfies MovementDirection;
  const quantityDelta = signedQuantityDelta(movementType, magnitude, direction);

  const reasonRaw = formData.get("reason");
  const reason =
    typeof reasonRaw === "string" && reasonRaw.trim() !== ""
      ? reasonRaw
      : undefined;

  const body: {
    movement_type: string;
    quantity_delta: number;
    reason?: string;
  } = { movement_type: movementType, quantity_delta: quantityDelta };
  if (reason !== undefined) {
    body.reason = reason;
  }

  const result = await adminBackendFetch(
    `/admin/products/${productId}/variants/${variantId}/stock/movements`,
    { method: "POST", body },
  );

  if (result.outcome === "unauthenticated") {
    redirect(ADMIN_LOGIN_PATH);
  }

  if (result.outcome === "backend_unavailable") {
    return { error: BACKEND_UNAVAILABLE_MESSAGE };
  }

  if (result.status === 201) {
    revalidatePath(adminProductDetailPath(productId));
    return { error: null };
  }

  return { error: extractAdminError(result.status, result.body) };
}

export async function retireVariantAction(formData: FormData): Promise<void> {
  const productId = String(formData.get("product-id") ?? "");
  const variantId = String(formData.get("variant-id") ?? "");
  const result = await adminBackendFetch(
    `/admin/products/${productId}/variants/${variantId}`,
    { method: "DELETE" },
  );

  if (result.outcome === "unauthenticated") {
    redirect(ADMIN_LOGIN_PATH);
  }

  revalidatePath(ADMIN_PRODUCTS_PATH);
}
