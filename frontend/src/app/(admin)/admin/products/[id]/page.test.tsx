import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

/**
 * `/admin/products/[id]` — edit page. A Server Component fetching
 * `/api/admin/products/{id}` (same same-origin, cookie-forwarding
 * pattern as `products/page.tsx` — server-to-server RSC fetches do NOT
 * automatically carry the visiting browser's cookies). Renders
 * `product-form.tsx` wired to `updateProductAction`, bound to this
 * product's id; no slug field exposed anywhere (spec: "the edit form
 * MUST NOT expose a slug field to change").
 *
 * @see design.md "Data Flow", tasks.md 4.13
 */

const NOT_FOUND = vi.fn();

vi.mock("next/headers", () => ({
  headers: vi.fn(
    async () =>
      new Headers({ host: "localhost:3000", cookie: "sb-access-token=abc" }),
  ),
}));

vi.mock("next/navigation", () => ({
  notFound: (...args: unknown[]) => {
    NOT_FOUND(...args);
    throw new Error("NEXT_NOT_FOUND");
  },
}));

async function importPage() {
  const mod = await import("./page");
  return mod.default;
}

function paramsFor(id: string) {
  return { params: Promise.resolve({ id }) };
}

describe("EditProductPage", () => {
  afterEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
  });

  it("fetches the product via /api/admin/products/{id}, forwarding the request cookie, and prefills the form", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          id: "p1",
          slug: "funda-iphone-15",
          name: "Funda iPhone 15",
          model: "iPhone 15",
          variants: [
            { id: "v1", color: "negro", price: "5000.00", cost: "2000.00" },
          ],
        }),
    } as Response);

    const EditProductPage = await importPage();
    const jsx = await EditProductPage(paramsFor("p1"));
    render(jsx);

    expect(screen.getByLabelText(/^name$/i)).toHaveValue("Funda iPhone 15");
    expect(screen.getByLabelText(/^model$/i)).toHaveValue("iPhone 15");
    expect(screen.getByLabelText(/color/i)).toHaveValue("negro");
    expect(screen.queryByLabelText(/slug/i)).not.toBeInTheDocument();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [requestUrl, requestInit] = fetchSpy.mock.calls[0];
    expect(String(requestUrl)).toBe(
      "http://localhost:3000/api/admin/products/p1",
    );
    expect((requestInit as RequestInit).headers).toMatchObject({
      cookie: "sb-access-token=abc",
    });
  });

  it("calls notFound() when the proxy route reports the product does not exist", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      status: 404,
      json: () => Promise.resolve({ error: "not_found" }),
    } as Response);

    const EditProductPage = await importPage();

    await expect(EditProductPage(paramsFor("missing"))).rejects.toThrow();
    expect(NOT_FOUND).toHaveBeenCalledTimes(1);
  });
});
