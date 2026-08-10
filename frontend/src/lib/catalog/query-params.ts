/**
 * Pure parsing/validation for the `/api/catalog` search & pagination
 * contract. Zero Next.js/Supabase imports so this module is unit-testable
 * on its own and shared by the Route Handler (PR3) and any page-level
 * search-param reading.
 *
 * @see design.md "Route Handler Contract — GET /api/catalog"
 */

export const MAX_SEARCH_TERM_LENGTH = 80;
export const DEFAULT_PAGE = 1;
export const DEFAULT_LIMIT = 12;
export const MIN_LIMIT = 1;
export const MAX_LIMIT = 48;

// PostgREST filter-syntax metacharacters. Stripping these before a term
// reaches `.or("name.ilike.%<term>%,...")` prevents a visitor from injecting
// additional filter clauses or wildcard operators via the search box.
const POSTGREST_METACHARACTERS = /[,.()"\\*%]/g;

export function sanitizeSearchTerm(raw: string): string {
  return raw
    .trim()
    .replace(POSTGREST_METACHARACTERS, "")
    .slice(0, MAX_SEARCH_TERM_LENGTH);
}

export type ParamParseResult<T> =
  | { ok: true; value: T }
  | { ok: false; reason: string };

function parsePositiveIntParam(
  raw: string | null,
  defaultValue: number,
  min: number,
  max: number,
  reason: string,
): ParamParseResult<number> {
  if (raw === null) {
    return { ok: true, value: defaultValue };
  }

  const value = Number(raw);
  if (!Number.isInteger(value) || value < min || value > max) {
    return { ok: false, reason };
  }

  return { ok: true, value };
}

export function parsePageParam(raw: string | null): ParamParseResult<number> {
  return parsePositiveIntParam(
    raw,
    DEFAULT_PAGE,
    1,
    Number.MAX_SAFE_INTEGER,
    "invalid_page",
  );
}

export function parseLimitParam(
  raw: string | null,
): ParamParseResult<number> {
  return parsePositiveIntParam(
    raw,
    DEFAULT_LIMIT,
    MIN_LIMIT,
    MAX_LIMIT,
    "invalid_limit",
  );
}
