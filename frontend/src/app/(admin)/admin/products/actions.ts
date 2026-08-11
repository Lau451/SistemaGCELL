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

const ADMIN_LOGIN_PATH = "/admin/login";
const ADMIN_PRODUCTS_PATH = "/admin/products";
const BACKEND_UNAVAILABLE_MESSAGE =
  "Unable to reach the server. Please try again.";

export interface ProductFormState {
  error: string | null;
}

interface VariantWritePayload {
  id?: string;
  color: string;
  price: string;
  cost: string;
}

interface ProductWritePayload {
  name: string;
  model: string;
  variants: VariantWritePayload[];
}

function buildVariantsPayload(formData: FormData): VariantWritePayload[] {
  const ids = formData.getAll("variant-id");
  const colors = formData.getAll("variant-color");
  const prices = formData.getAll("variant-price");
  const costs = formData.getAll("variant-cost");

  const variants: VariantWritePayload[] = [];
  for (let index = 0; index < colors.length; index += 1) {
    const rawId = ids[index];
    const id =
      typeof rawId === "string" && rawId.trim() !== "" ? rawId : undefined;

    variants.push({
      ...(id !== undefined ? { id } : {}),
      color: String(colors[index] ?? ""),
      // Verbatim strings — see the file-level money-precision note.
      price: String(prices[index] ?? ""),
      cost: String(costs[index] ?? ""),
    });
  }
  return variants;
}

function buildProductPayload(formData: FormData): ProductWritePayload {
  return {
    name: String(formData.get("name") ?? ""),
    model: String(formData.get("model") ?? ""),
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
