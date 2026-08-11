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
