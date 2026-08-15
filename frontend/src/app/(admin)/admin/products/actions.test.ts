import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `createProductAction` / `updateProductAction` / `retireProductAction` /
 * `retireVariantAction` — Server Actions relaying writes directly through
 * `adminBackendFetch` (design.md's "Decision: no write Route Handlers —
 * Server Actions relay directly"). `adminBackendFetch`, `redirect`, and
 * `revalidatePath` are all mocked so this proves the outcome-branching
 * contract in isolation, without a live backend.
 *
 * The money-precision test is this file's highest-value case
 * (design.md's threat matrix, item 5: "no `float`/`parseFloat` anywhere
 * in the write path"): a variant price/cost `FormData` value must reach
 * `adminBackendFetch`'s `body` as the EXACT submitted string, never
 * round-tripped through a JS `number`.
 */

const ADMIN_BACKEND_FETCH = vi.fn();
const REDIRECT = vi.fn();
const REVALIDATE_PATH = vi.fn();

vi.mock("@/lib/admin/backend-fetch", () => ({
  adminBackendFetch: (...args: unknown[]) => ADMIN_BACKEND_FETCH(...args),
}));

vi.mock("next/navigation", () => ({
  redirect: (...args: unknown[]) => REDIRECT(...args),
}));

vi.mock("next/cache", () => ({
  revalidatePath: (...args: unknown[]) => REVALIDATE_PATH(...args),
}));

async function importActions() {
  return import("./actions");
}

function formDataFor(fields: Record<string, string | string[]>) {
  const data = new FormData();
  for (const [key, value] of Object.entries(fields)) {
    if (Array.isArray(value)) {
      for (const entry of value) {
        data.append(key, entry);
      }
    } else {
      data.set(key, value);
    }
  }
  return data;
}

describe("createProductAction", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("on 201, revalidates and redirects to the products list", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 201,
      body: { id: "p1", slug: "funda-iphone-15" },
    });

    const { createProductAction } = await importActions();
    await createProductAction(
      { error: null },
      formDataFor({ name: "Funda iPhone 15", model: "iPhone 15" }),
    );

    expect(REVALIDATE_PATH).toHaveBeenCalledWith("/admin/products");
    expect(REDIRECT).toHaveBeenCalledWith("/admin/products");
  });

  it("on 422, returns an error state and does NOT redirect", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 422,
      body: { detail: "Field required" },
    });

    const { createProductAction } = await importActions();
    const result = await createProductAction(
      { error: null },
      formDataFor({ name: "", model: "" }),
    );

    expect(result.error).toBe("Field required");
    expect(REDIRECT).not.toHaveBeenCalled();
    expect(REVALIDATE_PATH).not.toHaveBeenCalled();
  });

  it("on unauthenticated outcome, redirects to /admin/login", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({ outcome: "unauthenticated" });

    const { createProductAction } = await importActions();
    await createProductAction(
      { error: null },
      formDataFor({ name: "Funda iPhone 15", model: "iPhone 15" }),
    );

    expect(REDIRECT).toHaveBeenCalledWith("/admin/login");
  });

  it("relays the POST to /admin/products", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 201,
      body: { id: "p1" },
    });

    const { createProductAction } = await importActions();
    await createProductAction(
      { error: null },
      formDataFor({ name: "Funda iPhone 15", model: "iPhone 15" }),
    );

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/products",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("MONEY PRECISION: relays variant price/cost as the exact submitted string, never a JS number", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 201,
      body: { id: "p1" },
    });

    const { createProductAction } = await importActions();
    await createProductAction(
      { error: null },
      formDataFor({
        name: "Funda iPhone 15",
        model: "iPhone 15",
        "variant-id": [""],
        "variant-color": ["negro"],
        // `0.10` as a JS number loses its trailing zero (`0.1`), and
        // `1234.567` exceeds 2-decimal money precision entirely — both
        // must reach the backend byte-for-byte, proving no
        // `parseFloat`/`Number()` round-trip anywhere in this path.
        "variant-price": ["0.10"],
        "variant-cost": ["1234.567"],
      }),
    );

    const [, init] = ADMIN_BACKEND_FETCH.mock.calls[0] as [
      string,
      { body: { variants: Array<{ price: unknown; cost: unknown }> } },
    ];
    const [variant] = init.body.variants;

    expect(variant.price).toBe("0.10");
    expect(typeof variant.price).toBe("string");
    expect(variant.cost).toBe("1234.567");
    expect(typeof variant.cost).toBe("string");
  });
});

describe("updateProductAction", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("relays a PATCH to /admin/products/{id} bound to the product id", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: { id: "p1" },
    });

    const { updateProductAction } = await importActions();
    await updateProductAction(
      "p1",
      { error: null },
      formDataFor({ name: "iPhone 15 Pro", model: "iPhone 15 Pro" }),
    );

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/products/p1",
      expect.objectContaining({ method: "PATCH" }),
    );
    expect(REVALIDATE_PATH).toHaveBeenCalledWith("/admin/products");
    expect(REDIRECT).toHaveBeenCalledWith("/admin/products");
  });

  it("on 422, returns an error state and does NOT redirect", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 422,
      body: { detail: "ProductVariant.price cannot be negative" },
    });

    const { updateProductAction } = await importActions();
    const result = await updateProductAction(
      "p1",
      { error: null },
      formDataFor({ name: "iPhone 15 Pro", model: "iPhone 15 Pro" }),
    );

    expect(result.error).toBe("ProductVariant.price cannot be negative");
    expect(REDIRECT).not.toHaveBeenCalled();
  });
});

describe("retireProductAction", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("relays a DELETE and revalidates the products list", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 204,
      body: null,
    });

    const { retireProductAction } = await importActions();
    await retireProductAction(formDataFor({ "product-id": "p1" }));

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/products/p1",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(REVALIDATE_PATH).toHaveBeenCalledWith("/admin/products");
  });

  it("on unauthenticated outcome, redirects to /admin/login", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({ outcome: "unauthenticated" });

    const { retireProductAction } = await importActions();
    await retireProductAction(formDataFor({ "product-id": "p1" }));

    expect(REDIRECT).toHaveBeenCalledWith("/admin/login");
  });
});

describe("uploadProductImageAction", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("relays the uploaded File to adminBackendFetch without buffering it (design.md Decision 8)", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 201,
      body: { id: "img1" },
    });

    const file = new File(["binary-bytes"], "photo.webp", {
      type: "image/webp",
    });
    // Reading the file into memory (`.arrayBuffer()`/`.text()`) before
    // relay would defeat the point of a multipart passthrough — the
    // Server Action must forward the `File` object itself.
    const arrayBufferSpy = vi.spyOn(file, "arrayBuffer");
    const textSpy = vi.spyOn(file, "text");

    const formData = new FormData();
    formData.set("file", file);

    const { uploadProductImageAction } = await importActions();
    await uploadProductImageAction("p1", { error: null }, formData);

    expect(arrayBufferSpy).not.toHaveBeenCalled();
    expect(textSpy).not.toHaveBeenCalled();

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledTimes(1);
    const [path, init] = ADMIN_BACKEND_FETCH.mock.calls[0] as [
      string,
      { method: string; body: FormData },
    ];
    expect(path).toBe("/admin/products/p1/images");
    expect(init.method).toBe("POST");
    // Same `File` instance, by identity — not a copy, not re-read.
    expect(init.body.get("file")).toBe(file);
  });

  it("relays optional variant-id and alt-text as variant_id/alt_text form fields", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 201,
      body: { id: "img1" },
    });

    const file = new File(["binary-bytes"], "photo.webp", {
      type: "image/webp",
    });
    const formData = new FormData();
    formData.set("file", file);
    formData.set("variant-id", "v1");
    formData.set("alt-text", "Front view");

    const { uploadProductImageAction } = await importActions();
    await uploadProductImageAction("p1", { error: null }, formData);

    const [, init] = ADMIN_BACKEND_FETCH.mock.calls[0] as [
      string,
      { body: FormData },
    ];
    expect(init.body.get("variant_id")).toBe("v1");
    expect(init.body.get("alt_text")).toBe("Front view");
  });

  it("omits variant_id/alt_text when not provided", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 201,
      body: { id: "img1" },
    });

    const file = new File(["binary-bytes"], "photo.webp", {
      type: "image/webp",
    });
    const formData = new FormData();
    formData.set("file", file);

    const { uploadProductImageAction } = await importActions();
    await uploadProductImageAction("p1", { error: null }, formData);

    const [, init] = ADMIN_BACKEND_FETCH.mock.calls[0] as [
      string,
      { body: FormData },
    ];
    expect(init.body.has("variant_id")).toBe(false);
    expect(init.body.has("alt_text")).toBe(false);
  });

  it("on 201, revalidates the product detail page and clears the error", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 201,
      body: { id: "img1" },
    });

    const formData = new FormData();
    formData.set(
      "file",
      new File(["binary-bytes"], "photo.webp", { type: "image/webp" }),
    );

    const { uploadProductImageAction } = await importActions();
    const result = await uploadProductImageAction(
      "p1",
      { error: null },
      formData,
    );

    expect(REVALIDATE_PATH).toHaveBeenCalledWith("/admin/products/p1");
    expect(result.error).toBeNull();
  });

  it("on 422, returns an error state and does NOT revalidate", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 422,
      body: { detail: "unsupported_image_format" },
    });

    const formData = new FormData();
    formData.set(
      "file",
      new File(["binary-bytes"], "photo.webp", { type: "image/webp" }),
    );

    const { uploadProductImageAction } = await importActions();
    const result = await uploadProductImageAction(
      "p1",
      { error: null },
      formData,
    );

    expect(result.error).toBe("unsupported_image_format");
    expect(REVALIDATE_PATH).not.toHaveBeenCalled();
  });

  it("on unauthenticated outcome, redirects to /admin/login", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({ outcome: "unauthenticated" });

    const formData = new FormData();
    formData.set(
      "file",
      new File(["binary-bytes"], "photo.webp", { type: "image/webp" }),
    );

    const { uploadProductImageAction } = await importActions();
    await uploadProductImageAction("p1", { error: null }, formData);

    expect(REDIRECT).toHaveBeenCalledWith("/admin/login");
  });
});

describe("deleteProductImageAction", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("relays a DELETE to the image sub-path and revalidates the product detail page", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 204,
      body: null,
    });

    const { deleteProductImageAction } = await importActions();
    await deleteProductImageAction(
      formDataFor({ "product-id": "p1", "image-id": "img1" }),
    );

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/products/p1/images/img1",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(REVALIDATE_PATH).toHaveBeenCalledWith("/admin/products/p1");
  });

  it("on unauthenticated outcome, redirects to /admin/login", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({ outcome: "unauthenticated" });

    const { deleteProductImageAction } = await importActions();
    await deleteProductImageAction(
      formDataFor({ "product-id": "p1", "image-id": "img1" }),
    );

    expect(REDIRECT).toHaveBeenCalledWith("/admin/login");
  });
});

describe("reorderProductImagesAction", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("relays a PUT with the ordered image id list as JSON and revalidates on 200", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 200,
      body: [{ id: "img2" }, { id: "img1" }],
    });

    const { reorderProductImagesAction } = await importActions();
    const result = await reorderProductImagesAction("p1", ["img2", "img1"]);

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/products/p1/images/order",
      expect.objectContaining({
        method: "PUT",
        body: { image_ids: ["img2", "img1"] },
      }),
    );
    expect(REVALIDATE_PATH).toHaveBeenCalledWith("/admin/products/p1");
    expect(result.error).toBeNull();
  });

  it("on 404 (foreign image id), returns an error state and does NOT revalidate", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 404,
      body: { detail: "Image not found" },
    });

    const { reorderProductImagesAction } = await importActions();
    const result = await reorderProductImagesAction("p1", ["img2", "img1"]);

    expect(result.error).toBe("Image not found");
    expect(REVALIDATE_PATH).not.toHaveBeenCalled();
  });

  it("on unauthenticated outcome, redirects to /admin/login", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({ outcome: "unauthenticated" });

    const { reorderProductImagesAction } = await importActions();
    await reorderProductImagesAction("p1", ["img2", "img1"]);

    expect(REDIRECT).toHaveBeenCalledWith("/admin/login");
  });
});

describe("retireVariantAction", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("relays a DELETE to the variant sub-path", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({
      outcome: "response",
      status: 204,
      body: null,
    });

    const { retireVariantAction } = await importActions();
    await retireVariantAction(
      formDataFor({ "product-id": "p1", "variant-id": "v1" }),
    );

    expect(ADMIN_BACKEND_FETCH).toHaveBeenCalledWith(
      "/admin/products/p1/variants/v1",
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(REVALIDATE_PATH).toHaveBeenCalledWith("/admin/products");
  });

  it("on unauthenticated outcome, redirects to /admin/login", async () => {
    ADMIN_BACKEND_FETCH.mockResolvedValue({ outcome: "unauthenticated" });

    const { retireVariantAction } = await importActions();
    await retireVariantAction(
      formDataFor({ "product-id": "p1", "variant-id": "v1" }),
    );

    expect(REDIRECT).toHaveBeenCalledWith("/admin/login");
  });
});
