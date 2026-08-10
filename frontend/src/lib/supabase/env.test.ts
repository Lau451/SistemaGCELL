import { afterEach, describe, expect, it } from "vitest";
import { getCatalogSupabaseEnv } from "./env";

const ORIGINAL_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ORIGINAL_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

afterEach(() => {
  process.env.NEXT_PUBLIC_SUPABASE_URL = ORIGINAL_URL;
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = ORIGINAL_ANON_KEY;
});

describe("getCatalogSupabaseEnv", () => {
  it("returns the url and anon key when both are set", () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "http://127.0.0.1:54321";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-anon-key";

    expect(getCatalogSupabaseEnv()).toEqual({
      url: "http://127.0.0.1:54321",
      anonKey: "test-anon-key",
    });
  });

  it("throws when NEXT_PUBLIC_SUPABASE_URL is missing", () => {
    delete process.env.NEXT_PUBLIC_SUPABASE_URL;
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-anon-key";

    expect(() => getCatalogSupabaseEnv()).toThrow(
      /NEXT_PUBLIC_SUPABASE_URL/,
    );
  });

  it("throws when NEXT_PUBLIC_SUPABASE_ANON_KEY is missing", () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "http://127.0.0.1:54321";
    delete process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

    expect(() => getCatalogSupabaseEnv()).toThrow(
      /NEXT_PUBLIC_SUPABASE_ANON_KEY/,
    );
  });
});
