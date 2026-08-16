# Apply Progress: Admin Low-Stock Alerts

Single apply batch — all 20 tasks (Phases 1-5) completed, frontend-only, single PR.

## Status: DONE (20/20 tasks)

## Files Created

- `frontend/src/app/(admin)/admin/stock-alert-badge.tsx` — async Server Component `StockAlertBadge`. `fetchLowStockCount()` mirrors `stock/page.tsx`'s `fetchAdminStock` cookie-forwarding idiom (`headers()` → `host` / `x-forwarded-proto` / `cookie`, same-origin `fetch`, `cache: "no-store"`), hits `GET /api/admin/stock?below=5` (fixed literal, D5), and returns `rows.length` — or `null` — from a single `try/catch` wrapping the fetch, the `!response.ok` check, and `response.json()` (design.md Decision 2). `StockAlertBadge` returns `null` when `count === null || count === 0` (D6); otherwise `<span className="text-destructive ml-1 text-xs font-medium">({count})</span>` — the literal classes from `products/page.tsx:111` / `stock/page.tsx:164` (D7).
- `frontend/src/app/(admin)/admin/stock-alert-badge.test.tsx` — 6 cases: fetch URL is exactly `…/api/admin/stock?below=5` with the cookie header forwarded; 3 rows → `(3)` carrying `text-destructive`; `[]` → `null`; `fetch` reject (network) → `null`; `!response.ok` (401) → `null`; `response.json()` throw (malformed body) → `null`. `vi.mock("next/headers")` + `vi.spyOn(globalThis, "fetch")`, same idiom as `stock/page.test.tsx`.

## Files Modified

- `frontend/src/app/(admin)/admin/layout.tsx` — imported `Suspense` from `react` and `StockAlertBadge` from `./stock-alert-badge`; the existing `<Link href="/admin/stock">` now renders `Stock{" "}` followed by `<Suspense fallback={null}><StockAlertBadge /></Suspense>` so the accessible name becomes `Stock (3)` once the count streams in. `AdminLayout` itself stays a synchronous Server Component — no `async` added, matching design.md Decision 1 (rejected the "make the layout async" alternative because it would block the whole shell and force a rewrite of all four existing `layout.test.tsx` cases).
- `frontend/src/app/(admin)/admin/layout.test.tsx` — added `vi.mock("./stock-alert-badge", () => ({ StockAlertBadge: () => <span>BADGE_STUB</span> }))`, a **synchronous** stub, because RTL cannot client-render an async RSC under `Suspense` (design.md Testing Strategy finding). Added one new case asserting the stub renders inside the `/admin/stock` link's subtree. The 4 pre-existing cases (children pass-through, Products link, Stock link href, sign-out submission) are unmodified.
- `openspec/changes/admin-low-stock-alerts/tasks.md` — all 20 checkboxes marked `[x]`.

## Test Results

- Focused (Phase 1, RED confirmed): `npm test -- --run stock-alert-badge` before `stock-alert-badge.tsx` existed — `Error: Failed to resolve import "./stock-alert-badge"`, 1 suite failed, 0 tests ran.
- Focused (Phase 2, GREEN confirmed): `npm test -- --run stock-alert-badge` after the component was created — 6/6 passed.
- Focused (Phase 3, RED confirmed): `npm test -- --run layout` after adding the new badge case but before wiring `layout.tsx` — 1 failed (`Unable to find an element with the text: BADGE_STUB`), 4 pre-existing cases passed unmodified.
- Focused (Phase 4, GREEN confirmed): `npm test -- --run layout` after wiring `Suspense`/`StockAlertBadge` into `layout.tsx` — 5/5 passed.
- Full frontend suite (Phase 5.1): `npm test -- --run` — 45 test files, 302 tests, all passed. No regressions in `products/page.test.tsx`, `stock/page.test.tsx`, or any other admin test.
- Type-check: `npx tsc --noEmit` — clean, zero errors.
- `git diff --stat -- frontend/src/app/api/admin/stock/route.ts backend/ supabase/migrations/ "frontend/src/app/(admin)/admin/page.tsx"` — empty diff, confirming Phase 5.2/5.3: the proxy route, every backend file, every migration, and the `/admin` landing page are byte-identical to `main`.
- `git diff --stat` (full change) — only `frontend/src/app/(admin)/admin/layout.tsx`, `layout.test.tsx`, plus the two new `stock-alert-badge.*` files (untracked). Zero backend files, zero migration files touched.

## TDD Cycle Evidence

| Task | RED | GREEN | REFACTOR |
|---|---|---|---|
| 1.1-1.8 / 2.1-2.4 | `stock-alert-badge.test.tsx` (6 cases) failed on import resolution — `stock-alert-badge.tsx` did not exist yet | `stock-alert-badge.tsx` created (fetch + count + safe-null); all 6 cases pass | None needed |
| 3.1-3.3 / 4.1-4.2 | New "renders the low-stock badge inside the Stock link" case in `layout.test.tsx` failed (`BADGE_STUB` not found) before `layout.tsx` was wired; 4 pre-existing cases stayed green throughout | `Suspense`/`StockAlertBadge` wired into the Stock `<Link>`; all 5 `layout.test.tsx` cases pass | None needed |

## Deviations From Design

None. Implementation matches design.md exactly: `stock-alert-badge.tsx` is a new, isolated async RSC (Decision 1), mounted via `<Suspense fallback={null}>` with `AdminLayout` staying synchronous; all three failure modes (network throw, `!ok`, `json()` parse throw) collapse to `null` inside one `try/catch` in `fetchLowStockCount()` (Decision 2); the count is `rows.length` with no client-side re-filtering, since `?below=5` already narrows server-side; styling reuses the literal `text-destructive ml-1 text-xs font-medium` classes (D7) rather than inventing a new convention. No backend file, proxy route, or migration touched (D3/D5).

## Issues Found

None.
