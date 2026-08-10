import { describe, expect, it } from "vitest";

/**
 * Server Components are not rendered in jsdom (design.md "Testing
 * Strategy") — instead, this imports each `page.tsx` module directly and
 * asserts its `export const revalidate === 300`, without ever calling the
 * default-exported async component. This also doubles as a smoke test
 * that the module graph (including the `server-only`-guarded Supabase
 * client chain) is import-safe under Vitest.
 */
describe("catalog page route-segment config", () => {
  it("(public)/page.tsx exports revalidate = 300", async () => {
    const mod = await import("./page");
    expect(mod.revalidate).toBe(300);
  });

  it("(public)/catalog/page.tsx exports revalidate = 300", async () => {
    const mod = await import("./catalog/page");
    expect(mod.revalidate).toBe(300);
  });

  it("(public)/catalog/page.tsx sets the canonical URL back to /", async () => {
    const mod = await import("./catalog/page");
    expect(mod.metadata).toEqual({ alternates: { canonical: "/" } });
  });

  it("(public)/product/[slug]/page.tsx exports revalidate = 300", async () => {
    const mod = await import("./product/[slug]/page");
    expect(mod.revalidate).toBe(300);
  });
});
