import { readFileSync, readdirSync, statSync } from "node:fs";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

/**
 * Cross-cutting regression guard (Phase 4, task 4.1) extending the
 * "Structural Guarantee: cost / exact stock unreachable" source-grep
 * pattern (design.md, originally scoped to `queries.ts`) to every
 * production source file across all three PRs of this capability:
 * public pages, catalog components (incl. the Route Handler's
 * client-side consumer), and the `/api/catalog` Route Handler itself.
 *
 * A live rendered-HTML + JSON-response check against the real local
 * Supabase seed was additionally performed manually during `sdd-apply`
 * (see apply-progress "Work Unit Evidence") — this automated test is the
 * durable, CI-repeatable half of task 4.1: no production source file in
 * these directories may reference a `cost` or stock-quantity token at
 * all, which is a stronger, earlier-failing guarantee than inspecting
 * output after the fact.
 */

const FRONTEND_SRC_DIR = join(
  fileURLToPath(import.meta.url),
  "..",
  "..",
  "..",
  "..",
);

const SCANNED_DIRECTORIES = [
  join(FRONTEND_SRC_DIR, "app", "(public)"),
  join(FRONTEND_SRC_DIR, "app", "api", "catalog"),
  join(FRONTEND_SRC_DIR, "components", "catalog"),
];

const SOURCE_EXTENSIONS = new Set([".ts", ".tsx"]);
// Matches `cost`, `quantity`, `quantity_on_hand` etc. as a whole identifier
// segment — but not e.g. `costume`/`accost` (would be over-broad) since the
// codebase has no such words, this simple substring check is sufficient
// and deliberately stricter than a word-boundary regex.
const FORBIDDEN_TOKENS = ["cost", "quantity"];

function listSourceFiles(dir: string): string[] {
  const entries = readdirSync(dir);
  const files: string[] = [];

  for (const entry of entries) {
    const fullPath = join(dir, entry);
    const stats = statSync(fullPath);

    if (stats.isDirectory()) {
      files.push(...listSourceFiles(fullPath));
      continue;
    }

    if (SOURCE_EXTENSIONS.has(extname(entry)) && !entry.endsWith(".test.tsx") && !entry.endsWith(".test.ts")) {
      files.push(fullPath);
    }
  }

  return files;
}

describe("sensitive-field regression guard: cost/quantity never referenced in catalog UI/API source", () => {
  const files = SCANNED_DIRECTORIES.flatMap((dir) => listSourceFiles(dir));

  it("finds a non-trivial number of production source files to scan", () => {
    // Proves the scan actually exercised real files, not an empty/missing
    // directory silently passing.
    expect(files.length).toBeGreaterThanOrEqual(8);
  });

  it.each(FORBIDDEN_TOKENS)(
    "no scanned file contains the forbidden token '%s'",
    (token) => {
      const offenders = files.filter((file) =>
        readFileSync(file, "utf-8").toLowerCase().includes(token),
      );
      expect(offenders).toEqual([]);
    },
  );
});
