import { describe, expect, it } from "vitest";
import { PRODUCT_PHOTOS_BUCKET, toPublicPhotoUrl } from "./storage-url";

describe("toPublicPhotoUrl", () => {
  it("builds a public storage URL against the local Supabase instance", () => {
    expect(
      toPublicPhotoUrl("http://127.0.0.1:54321", "fundas-iphone-15/negro.jpg"),
    ).toBe(
      "http://127.0.0.1:54321/storage/v1/object/public/product-photos/fundas-iphone-15/negro.jpg",
    );
  });

  it("builds a public storage URL against a hosted Supabase project", () => {
    expect(
      toPublicPhotoUrl(
        "https://abcdefgh.supabase.co",
        "fundas-iphone-15/negro.jpg",
      ),
    ).toBe(
      "https://abcdefgh.supabase.co/storage/v1/object/public/product-photos/fundas-iphone-15/negro.jpg",
    );
  });

  it("does not duplicate the slash when the base URL has a trailing slash", () => {
    expect(toPublicPhotoUrl("http://127.0.0.1:54321/", "x.jpg")).toBe(
      "http://127.0.0.1:54321/storage/v1/object/public/product-photos/x.jpg",
    );
  });

  it("does not duplicate the slash when storage_path has a leading slash", () => {
    expect(toPublicPhotoUrl("http://127.0.0.1:54321", "/x.jpg")).toBe(
      "http://127.0.0.1:54321/storage/v1/object/public/product-photos/x.jpg",
    );
  });

  it("uses the product-photos bucket name", () => {
    expect(PRODUCT_PHOTOS_BUCKET).toBe("product-photos");
  });
});
