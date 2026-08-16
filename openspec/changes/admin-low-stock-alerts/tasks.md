# Tasks: Admin Low-Stock Alerts

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~180–230 (2 new files ~90 lines total, 2 modified files ~15 + ~40 lines) |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Ship `StockAlertBadge` + wire it into `admin/layout.tsx` behind `Suspense` | PR 1 (single) | `npm run test -- stock-alert-badge layout` (frontend workspace) | N/A — no backend/E2E harness in repo (vitest only, per design.md Testing Strategy) | `git revert` the single commit; removes new files and the layout/test additions, `/admin/*` shell unaffected |

## Phase 1: Badge Component — RED (failing unit tests first)

- [x] 1.1 Create `frontend/src/app/(admin)/admin/stock-alert-badge.test.tsx`: mock `next/headers` (`vi.mock("next/headers")`, same idiom as `stock/page.test.tsx`) and `vi.spyOn(globalThis, "fetch")`.
- [x] 1.2 RED test: fetch is called with URL exactly `…/api/admin/stock?below=5` (assert on the `fetch` mock's first call args), cookie header forwarded from `headers()`.
- [x] 1.3 RED test: `fetch` resolves `{ ok: true, json: () => [3 rows] }` → rendered output contains `(3)` with `text-destructive` class (per spec.md "non-zero count renders with destructive styling").
- [x] 1.4 RED test: `fetch` resolves `{ ok: true, json: () => [] }` → `StockAlertBadge()` returns `null` (D6, spec.md "zero low-stock count hides the badge entirely").
- [x] 1.5 RED test — failure mode 1: `fetch` rejects (network throw) → returns `null`, no throw escapes.
- [x] 1.6 RED test — failure mode 2: `fetch` resolves `{ ok: false }` (401/502) → returns `null`, no throw escapes.
- [x] 1.7 RED test — failure mode 3: `fetch` resolves `{ ok: true, json: () => { throw } }` (malformed body) → returns `null`, no throw escapes.
- [x] 1.8 Run `npm run test -- stock-alert-badge` and confirm all new cases fail (module doesn't exist yet) — RED confirmed.

## Phase 2: Badge Component — GREEN

- [x] 2.1 Create `frontend/src/app/(admin)/admin/stock-alert-badge.tsx`: async Server Component, mirrors `fetchAdminStock`'s cookie-forwarding idiom from `stock/page.tsx` (`headers()` → `host` / `x-forwarded-proto` / `cookie`, same-origin, `cache: "no-store"`), fixed `?below=5`.
- [x] 2.2 Implement `fetchLowStockCount()`: wraps fetch + `!response.ok` + `response.json()` in one try/catch collapsing all three failure modes to `null` (design.md Decision 2 — never throws).
- [x] 2.3 Implement `StockAlertBadge`: `count === null || count === 0` → return `null` (D6); else return `<span className="text-destructive ml-1 text-xs font-medium">({count})</span>` (D7, exact classes from `products/page.tsx:111` / `stock/page.tsx:164`).
- [x] 2.4 Run `npm run test -- stock-alert-badge` and confirm all cases from Phase 1 pass — GREEN confirmed.

## Phase 3: Layout Wiring — RED

- [x] 3.1 In `frontend/src/app/(admin)/admin/layout.test.tsx`, add `vi.mock("./stock-alert-badge", ...)` with a **sync** stub component (RTL cannot client-render an async RSC under `Suspense` — design.md finding), mirroring the existing `vi.mock("./actions")` idiom.
- [x] 3.2 RED test: stub renders a marker (e.g. `<span>BADGE_STUB</span>`) inside the Stock link's subtree; assert it is present after rendering `AdminLayout`.
- [x] 3.3 Run `npm run test -- layout` and confirm the new case fails (badge not yet wired) while the 4 existing cases still pass unmodified — RED confirmed.

## Phase 4: Layout Wiring — GREEN

- [x] 4.1 Modify `frontend/src/app/(admin)/admin/layout.tsx`: import `Suspense` from `react` and `StockAlertBadge` from `./stock-alert-badge`; wrap it in `<Suspense fallback={null}>` inside the existing `<Link href="/admin/stock">`, keeping `Stock{" "}` so the accessible name stays `Stock (3)` when populated (design.md Interfaces/Contracts). `AdminLayout` itself stays synchronous — no `async` added.
- [x] 4.2 Run `npm run test -- layout` and confirm all 5 cases (4 existing + 1 new) pass — GREEN confirmed.

## Phase 5: Verification

- [x] 5.1 Run the full frontend test suite (`npm run test`) to confirm no regressions in `products/page.test.tsx`, `stock/page.test.tsx`, or other admin tests.
- [x] 5.2 Manually cross-check `frontend/src/app/api/admin/stock/route.ts`, `backend/src/gcell/**`, `supabase/migrations/**`, and `(admin)/admin/page.tsx` remain byte-identical to `main` (proposal.md Affected Areas — all listed "Unchanged").
- [x] 5.3 Confirm `admin/page.tsx` landing page has zero new imports/widgets (Out of Scope: "Badge on the `/admin` landing page").
