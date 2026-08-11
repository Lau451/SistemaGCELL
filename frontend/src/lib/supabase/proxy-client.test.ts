import { afterEach, describe, expect, it } from "vitest";
import { NextRequest, NextResponse } from "next/server";
import { createProxyClient } from "./proxy-client";

/**
 * `createProxyClient` is runtime-coupled to `proxy.ts` (constructs a
 * Supabase client wired to a live `NextRequest`/`NextResponse` cookie
 * pair) — exercising a real session refresh would require a live
 * Supabase Auth service, which is out of scope for a unit test (see
 * design.md's Testing Strategy: that end-to-end path is the one manual
 * E2E check, not a pinned unit suite).
 *
 * Following the `revalidate.test.ts` pattern for logic-light,
 * runtime-coupled modules: this imports the module and constructs the
 * client against real `NextRequest`/`NextResponse` instances (both are
 * plain Web-standard-based classes, safe to construct outside an actual
 * server) without invoking any auth method that would trigger a network
 * call — doubling as a smoke test that the module graph, including the
 * `server-only`-guarded import chain, is import- and construction-safe
 * under Vitest.
 */
const ORIGINAL_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const ORIGINAL_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

afterEach(() => {
  process.env.NEXT_PUBLIC_SUPABASE_URL = ORIGINAL_URL;
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = ORIGINAL_ANON_KEY;
});

describe("createProxyClient", () => {
  it("constructs a Supabase client from a live NextRequest/NextResponse pair", () => {
    process.env.NEXT_PUBLIC_SUPABASE_URL = "http://127.0.0.1:54321";
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY = "test-anon-key";

    const request = new NextRequest("http://localhost/admin/products");
    const response = NextResponse.next();

    const client = createProxyClient(request, response);

    expect(client).toBeDefined();
    expect(client.auth).toBeDefined();
  });
});
