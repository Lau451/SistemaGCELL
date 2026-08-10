import { describe, expect, it } from "vitest";
import {
  buildProductPhotoPattern,
  PRODUCT_PHOTO_PATHNAME,
} from "./image-pattern";

describe("buildProductPhotoPattern", () => {
  it("builds a pattern for the local Supabase instance", () => {
    expect(buildProductPhotoPattern("http://127.0.0.1:54321")).toEqual({
      protocol: "http",
      hostname: "127.0.0.1",
      port: "54321",
      pathname: PRODUCT_PHOTO_PATHNAME,
      search: "",
    });
  });

  it("builds a pattern for a hosted Supabase project", () => {
    expect(
      buildProductPhotoPattern("https://abcdefgh.supabase.co"),
    ).toEqual({
      protocol: "https",
      hostname: "abcdefgh.supabase.co",
      port: "",
      pathname: PRODUCT_PHOTO_PATHNAME,
      search: "",
    });
  });

  it("always pins search to the empty string, never omitting it", () => {
    const local = buildProductPhotoPattern("http://127.0.0.1:54321");
    const hosted = buildProductPhotoPattern("https://abcdefgh.supabase.co");
    expect(local.search).toBe("");
    expect(hosted.search).toBe("");
  });

  it("scopes the pathname to the product-photos public storage prefix", () => {
    expect(PRODUCT_PHOTO_PATHNAME).toBe(
      "/storage/v1/object/public/product-photos/**",
    );
  });

  it("throws early on a malformed Supabase URL instead of returning garbage", () => {
    expect(() => buildProductPhotoPattern("not-a-url")).toThrow();
  });
});
