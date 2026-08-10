import { describe, expect, it } from "vitest";
import {
  DEFAULT_LIMIT,
  DEFAULT_PAGE,
  MAX_LIMIT,
  MAX_SEARCH_TERM_LENGTH,
  MIN_LIMIT,
  parseLimitParam,
  parsePageParam,
  sanitizeSearchTerm,
} from "./query-params";

describe("sanitizeSearchTerm", () => {
  it("trims surrounding whitespace", () => {
    expect(sanitizeSearchTerm("  funda  ")).toBe("funda");
  });

  // One case per PostgREST metacharacter class the design flags as
  // filter-syntax-injection-capable inside `.or("name.ilike.%q%,...")`.
  it.each([
    [",", "a,b"],
    [".", "a.b"],
    ["(", "a(b"],
    [")", "a)b"],
    ['"', 'a"b'],
    ["\\", "a\\b"],
    ["*", "a*b"],
    ["%", "a%b"],
  ])("strips the %s metacharacter class", (_label, raw) => {
    const result = sanitizeSearchTerm(raw);
    expect(result).toBe("ab");
  });

  it("strips every metacharacter class when combined", () => {
    expect(sanitizeSearchTerm('a,.()"\\*%b')).toBe("ab");
  });

  it("truncates a search term longer than 80 characters", () => {
    const raw = "a".repeat(200);
    const result = sanitizeSearchTerm(raw);
    expect(result).toHaveLength(MAX_SEARCH_TERM_LENGTH);
    expect(result).toBe("a".repeat(80));
  });

  it("leaves a term at exactly 80 characters untouched", () => {
    const raw = "a".repeat(80);
    expect(sanitizeSearchTerm(raw)).toBe(raw);
  });
});

describe("parsePageParam", () => {
  it("defaults to page 1 when absent", () => {
    expect(parsePageParam(null)).toEqual({ ok: true, value: DEFAULT_PAGE });
  });

  it("accepts a valid page number", () => {
    expect(parsePageParam("3")).toEqual({ ok: true, value: 3 });
  });

  it.each(["0", "-1", "abc"])("rejects page=%s", (raw) => {
    const result = parsePageParam(raw);
    expect(result.ok).toBe(false);
  });
});

describe("parseLimitParam", () => {
  it("defaults to 12 when absent", () => {
    expect(parseLimitParam(null)).toEqual({ ok: true, value: DEFAULT_LIMIT });
  });

  it("accepts a valid limit", () => {
    expect(parseLimitParam(String(MAX_LIMIT))).toEqual({
      ok: true,
      value: MAX_LIMIT,
    });
  });

  it("accepts the minimum limit", () => {
    expect(parseLimitParam(String(MIN_LIMIT))).toEqual({
      ok: true,
      value: MIN_LIMIT,
    });
  });

  it.each(["0", "-1", "abc", "999"])("rejects limit=%s", (raw) => {
    const result = parseLimitParam(raw);
    expect(result.ok).toBe(false);
  });
});
