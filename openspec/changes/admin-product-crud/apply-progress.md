# Apply Progress: Admin Product CRUD

## Batch 5 (Post-sdd-verify — Spec Correction, Coverage Gaps, Phase 5 Closure)

**Scope**: `sdd-verify` ran against the full 4-PR change (main @ `0dcdfd0`) and returned **FAIL** (1 CRITICAL, 0 WARNING, 3 SUGGESTION). The orchestrator resolved every finding directly, on `main`, without a separate PR branch — this work is documentation/test-only, no new production behavior, well under budget.

**CRITICAL finding, resolved**: `specs/product-persistence/spec.md`'s "Repository Soft-Delete Retires A Product Or Variant Without Row Deletion" requirement literally claimed soft-deleting a product marks "the product row **and both variant rows**... via `UPDATE`." The actual, deliberately-different implementation (`design.md`'s own "product retirement cascades at read time, not by stamping variants" decision, followed correctly by both adapters) stamps only the product row and hides variants via read-time join filtering. Unlike the Server-Actions-only divergence (explicitly reconciled in `design.md`'s Open Questions during PR4), this one was never reconciled back into `spec.md` — a pure spec-text/implementation mismatch, not a functional defect (the described end-user behavior — variants disappearing from every view after a product retires — was real and already well-tested). Fixed by rewriting the requirement and its scenario to describe the actual read-time-cascade mechanism, matching `design.md` and the already-correct `admin-product-management` spec (which only ever described the observable effect, not the mechanism).

**SUGGESTION #1, resolved**: two spec scenarios ("No Restore Capability", "No Show-Retired Filter") were PARTIAL — true only by static source-reading, with no runtime test that would catch either control being added by accident later. Added one new test to `page.test.tsx` ("never renders a restore control or a show-retired filter/toggle") asserting the negative via `screen.queryByText`/`queryByRole`, closing both scenarios to COMPLIANT with a real regression guard.

**SUGGESTION #2, resolved**: Phase 5 (tasks 5.1–5.5) was 0/5 checked in `tasks.md` despite 5.2–5.4 already being independently proven during verification.
- 5.1 (manual E2E, no Playwright in this repo): ran directly against the live stack — started FastAPI on port 8123 with the real `DB_URL`/`SUPABASE_JWKS_URL`/etc, signed in as the pre-existing `e2e-admin@gcell.local` test user via a real password grant against local Supabase Auth, then drove the full chain with real HTTP requests and a real JWT: `POST /admin/products` (201, slug auto-generated as `e2e-funda-de-prueba-grande`) → confirmed the row in the public `catalog_products` REST endpoint → `PATCH` (renamed name/model, changed the variant) → confirmed the slug stayed frozen in both the API response and the public catalog row → `DELETE` (204) → confirmed `GET /admin/products/{id}` now `404`, the product absent from `GET /admin/products`, and absent from `catalog_products`. Full create→edit→retire→gone chain proven on the real stack, not mocked. Backend process killed afterward (verified via a failed health check).
- 5.2/5.3: closed by SUGGESTION #1's new test above, plus `sdd-verify`'s own independent static confirmation.
- 5.4: full regression re-run — 163/163 backend (`DB_URL` set), 212/212 frontend (211 + the new negative-assertion test), `npx tsc --noEmit` clean, `npm run build` clean with all routes registered.
- 5.5 (README note "if project convention requires it"): checked `backend/README.md` (empty) and `frontend/README.md` (unmodified `create-next-app` boilerplate) — this project has no README-as-documentation convention; every prior archived change also left both untouched. N/A, correctly.

**SUGGESTION #3 (spec cross-reference comment)**: not applied — the corrected `product-persistence/spec.md` requirement text now directly explains the read-time-cascade mechanism and cites `design.md` by name inline, which serves the same purpose as a separate cross-reference comment without adding one.

**Files changed this batch**:
| File | Action |
|---|---|
| `openspec/changes/admin-product-crud/specs/product-persistence/spec.md` | Modified — CRITICAL fix |
| `frontend/src/app/(admin)/admin/products/page.test.tsx` | Modified — 1 new test |
| `openspec/changes/admin-product-crud/tasks.md` | Modified — Phase 5 all 5 tasks marked `[x]` |
| `openspec/changes/admin-product-crud/verify-report.md` | Pre-existing, not modified (kept as the historical FAIL record; this batch's fixes are what let a re-verify pass) |

**Verification**: 163/163 backend, 212/212 frontend, `tsc --noEmit` clean, `npm run build` clean, full manual E2E chain proven on the live stack.

**Status**: All 59 tasks across Phases 0–5 complete. Ready for a fresh `sdd-verify` pass (should now return PASS), then `sdd-archive`.

## Batch 4 (PR4 — Frontend)

**Scope**: Phase 4 (4.1–4.16), the pre-resolved "PR 4" work unit (`chain
strategy: stacked-to-main`, `delivery strategy: ask-on-risk`) from
`tasks.md`'s Review Workload Forecast. Branch `pr4-product-crud-frontend`
off `main` (`d6aef2e`, which already has PR1's migration, PR2's port/
adapters/use cases/slug generation, and PR3's API routes merged). No
backend file touched. No write Route Handler created — every write goes
through a Server Action relaying `adminBackendFetch`, per design.md's
"Decision: no write Route Handlers — Server Actions relay directly".
**Mode**: Strict TDD.

### Completed Tasks

- [x] 4.1 RED `backend-fetch.test.ts`: gate/relay/204/throw cases
- [x] 4.2 GREEN `backend-fetch.ts`: `adminBackendFetch`
- [x] 4.3 GREEN `route.ts` (refactor onto `adminBackendFetch`, GET only, existing test untouched)
- [x] 4.4 RED `[id]/route.test.ts`: single-product proxy
- [x] 4.5 GREEN `[id]/route.ts`
- [x] 4.6 RED `api-error.test.ts`: both `detail` shapes + fallback
- [x] 4.7 GREEN `api-error.ts`: `extractAdminError`
- [x] 4.8 RED `actions.test.ts`: all 4 actions + money-precision case
- [x] 4.9 GREEN `actions.ts`: `createProductAction`/`updateProductAction`/`retireProductAction`/`retireVariantAction`
- [x] 4.10 RED `product-form.test.tsx`: add/remove-unsaved/remove-saved/error
- [x] 4.11 GREEN `product-form.tsx`: client component, no slug field
- [x] 4.12 GREEN `new/page.tsx`
- [x] 4.13 RED+GREEN `[id]/page.tsx` (+ test): edit page
- [x] 4.14 GREEN `page.tsx` (modify): New/Edit/Retire; `page.test.tsx` updated
- [x] 4.15 RED extend `catalog-route-conformance.test.ts`: 3 new paths, zero `runtime-caching.ts` change
- [x] 4.16 Regression: full frontend suite green, 0 regressions

## Files Changed (Batch 4)

| File | Action | What Was Done |
|---|---|---|
| `frontend/src/lib/admin/backend-fetch.ts` | Created | `adminBackendFetch(path, init?)` — the one session-gate-then-relay implementation; `getClaims()` gates (fetch never called without claims), `getSession().access_token` relayed as Bearer, `204` special-cased before `.json()`, `JSON.stringify(body)` verbatim (no numeric coercion of price/cost) |
| `frontend/src/lib/admin/__tests__/backend-fetch.test.ts` | Created | 5 tests: unauthenticated (2 cases: no claims, empty claims), method/body/Bearer relay, `204`→`body:null` without calling `.json()`, thrown fetch→`backend_unavailable` |
| `frontend/src/app/api/admin/products/route.ts` | Modified | Refactored onto `adminBackendFetch`; still GET-only, no POST added; existing `route.test.ts` untouched and still green (refactor invisible to it, as designed — both mock the same two transitive modules) |
| `frontend/src/app/api/admin/products/[id]/route.ts` | Created | GET-one proxy for the edit page. **Deviation**: relays `GET /admin/products` (list) and filters server-side, rather than a backend `GET {id}` route — see Deviations below |
| `frontend/src/app/api/admin/products/[id]/__tests__/route.test.ts` | Created | 4 tests: unauthenticated, backend_unavailable, id-match-from-list, 404-when-absent |
| `frontend/src/lib/admin/api-error.ts` | Created | `extractAdminError(status, body)` — normalizes Pydantic's native list shape and this app's own `{"detail": "string"}` shape into one message; generic fallback otherwise |
| `frontend/src/lib/admin/__tests__/api-error.test.ts` | Created | 6 tests: single/multi Pydantic message, string shape (422 and 409), unrecognized-object fallback, null/string-body fallback |
| `frontend/src/app/(admin)/admin/products/actions.ts` | Created | `createProductAction`, `updateProductAction`, `retireProductAction`, `retireVariantAction` — all `"use server"`, all relay through `adminBackendFetch`; `buildVariantsPayload` zips parallel `variant-id`/`variant-color`/`variant-price`/`variant-cost` fields positionally via `formData.getAll()`, blank id = new; price/cost carried as `String(...)` of the raw `FormData` value, never `parseFloat`/`Number()` |
| `frontend/src/app/(admin)/admin/products/actions.test.ts` | Created | 11 tests across all 4 actions: 201→revalidate+redirect, 422→error state no redirect, unauthenticated→redirect `/admin/login`, POST/PATCH/DELETE path relaying, and the explicit **money-precision** test (`"0.10"` and `"1234.567"` proven to reach `adminBackendFetch`'s `body` as the exact string, still `typeof === "string"`) |
| `frontend/src/app/(admin)/admin/products/product-form.tsx` | Created | Client component shared by create/edit; `useActionState` wired to whichever `action` prop is passed; variant rows in `useState`, hidden `variant-id` per row (blank = new); removing an unsaved row is a local `setState` (no request); removing a saved row calls `retireVariantAction` directly (Server Actions are callable as plain async functions, not only via `<form action>`) inside a `useTransition`, then removes the row locally; price/cost inputs `type="number" step="0.01" min="0"`; no slug field anywhere |
| `frontend/src/app/(admin)/admin/products/product-form.test.tsx` | Created | 6 tests: labeled inputs + no slug field, add row, remove-unsaved (no request), remove-saved (submits `retireVariantAction` with correct `FormData`), error `role="alert"`, number-input attributes |
| `frontend/src/app/(admin)/admin/products/new/page.tsx` | Created | Renders `ProductForm` wired to `createProductAction` |
| `frontend/src/app/(admin)/admin/products/[id]/page.tsx` | Created | Server Component; fetches `/api/admin/products/{id}`, forwarding the incoming request's `cookie` header (same pattern as `products/page.tsx`); `notFound()` on a missing product; renders `ProductForm` wired to `updateProductAction.bind(null, product.id)`; no slug field exposed |
| `frontend/src/app/(admin)/admin/products/[id]/page.test.tsx` | Created | 2 tests: fetch+cookie-forward+prefill, `notFound()` called on a 404 from the proxy |
| `frontend/src/app/(admin)/admin/products/page.tsx` | Modified | Restructured to one row per PRODUCT (not per variant — see Deviations); added "New product" link, per-product Edit link, per-product Retire form (`retireProductAction`) |
| `frontend/src/app/(admin)/admin/products/page.test.tsx` | Modified | Rewrote/extended: grouped-row rendering, zero-variant product still listed, New-product link, Edit link, Retire-button submission, pre-existing error-state case preserved |
| `frontend/src/lib/pwa/__tests__/catalog-route-conformance.test.ts` | Modified | Extended `it.each` admin-paths table with `/admin/products/new`, `/admin/products/{uuid}`, `/api/admin/products/{uuid}` — all resolve `NetworkOnly` via the EXISTING `isAdminOrMutatingRequest` prefix matchers; zero source change to `runtime-caching.ts` (SHA256 pin unchanged) |
| `openspec/changes/admin-product-crud/tasks.md` | Modified | Phase 4 tasks (4.1–4.16) marked `[x]` with DONE notes |

## TDD Cycle Evidence (Strict TDD Mode, Batch 4)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 4.1/4.2 | `backend-fetch.test.ts` | Unit (mocked `createSessionClient` + spied `fetch`) | Pre-existing 170/170 baseline stayed green | Written and run: `Failed to resolve import "../backend-fetch"` (module didn't exist) | 5/5 passed after implementing `adminBackendFetch` | 5 cases: no-claims, empty-claims, method/body/Bearer relay, `204`→null, throw→`backend_unavailable` | Clean |
| 4.3 | `route.test.ts` (pre-existing, unmodified) | Integration | N/A — regression proof | N/A — this task is a refactor of already-passing code, not a new RED/GREEN cycle | 4/4 stayed green after the refactor, confirming it is byte-behaviorally invisible to this test | N/A | Clean |
| 4.4/4.5 | `[id]/route.test.ts` | Integration (mocked `adminBackendFetch`) | 5/5 (4.1/4.2) stayed green | Written and run: `Failed to resolve import "../route"` | 4/4 passed after implementing the list-filter proxy | 4 cases: unauthenticated, backend_unavailable, id-match, 404-absent | Clean |
| 4.6/4.7 | `api-error.test.ts` | Unit (pure function) | Stayed green throughout | Written and run: `Failed to resolve import "../api-error"` | 6/6 passed after implementing `extractAdminError` | 6 cases: single/multi Pydantic msg, 422 string, 409 string, object fallback, null/string fallback | Clean |
| 4.8/4.9 | `actions.test.ts` | Unit (mocked `adminBackendFetch`/`redirect`/`revalidatePath`) | Stayed green throughout | Written and run: `Failed to resolve import "./actions"` | 11/11 passed after implementing all 4 actions | 11 cases across 4 actions, including the dedicated money-precision case | Clean |
| 4.10/4.11 | `product-form.test.tsx` | Component (RTL + `userEvent`, mocked `retireVariantAction`) | Stayed green throughout | Written and run: `Failed to resolve import "./product-form"` | 6/6 passed after implementing `ProductForm` | 6 cases: no-slug, add-row, remove-unsaved, remove-saved, error-alert, number-input-attrs | Clean |
| 4.12 | (exercised via `product-form.test.tsx` + manual wiring) | N/A — thin page, no dedicated RED test per `tasks.md`'s own task list | N/A | N/A — `tasks.md` marks 4.12 GREEN-only | Verified by full-suite pass + `npm run build`'s route compilation | N/A | Clean |
| 4.13 | `[id]/page.test.tsx` | Component (RTL, mocked `next/headers`/`next/navigation`) | Stayed green throughout | Written and run: `Failed to resolve import "./page"` | 2/2 passed after implementing the edit page | 2 cases: fetch+cookie-forward+prefill, `notFound()` on missing product | Clean |
| 4.14 | `page.test.tsx` (rewritten) | Component (RTL + `userEvent`, mocked `next/headers` + `./actions`) | N/A — this task modifies the file the test targets | Written and run against the OLD `page.tsx`: 4/6 FAILED (no New-product link, no Edit link, no Retire button existed yet) | 6/6 passed after restructuring to one-row-per-product with New/Edit/Retire | 6 cases: grouped rendering, zero-variant product listed, New-product link, Edit link, Retire submission, pre-existing error state | Clean |
| 4.15 | `catalog-route-conformance.test.ts` (extended) | Unit (pure matcher functions + SHA256 pin) | Pre-existing 9/9 (8 route matches + 1 hash pin) in this file stayed green | Extended the `it.each` table; run immediately GREEN since the pre-existing prefix matchers already cover the new paths — this is the expected, hoped-for outcome per `tasks.md`'s "zero source change to `runtime-caching.ts` expected" framing, not a genuine RED-then-GREEN cycle | 12/12 passed, including the unchanged SHA256 pin (proving zero `runtime-caching.ts` edit) | 3 new cases: `/admin/products/new`, `/admin/products/{uuid}`, `/api/admin/products/{uuid}` | Clean |

### A note on 4.15's "no genuine RED" case

Unlike every other row above, extending `catalog-route-conformance.test.ts`
did NOT produce a failing run before the "implementation" — because there
was no implementation: `tasks.md` itself frames this task as "zero source
change to `runtime-caching.ts` expected" and instructs escalating clearly
rather than silently patching if that assumption turns out wrong. It
didn't: the existing `isAdminOrMutatingRequest` matcher's `/admin/`-prefix
and `/api/admin`-prefix checks already cover all 3 new paths, confirmed by
running the extended test immediately GREEN with zero
`runtime-caching.ts` edit (the SHA256 pin — a hash of that exact file —
stayed unchanged, which is itself the proof). This is a legitimate,
intentional exception to "every row is RED first," not a process gap.

### Test Summary (Batch 4)
- **Total tests written this batch**: 41 (5 backend-fetch + 4 id-route + 6 api-error + 11 actions + 6 product-form + 2 id-page + 4 net-new page.test.tsx cases [New-product link, Edit link, Retire submission, zero-variant listing] + 3 net-new catalog-route-conformance cases)
- **Total tests passing (frontend, full suite, no filter)**: 211/211 (was 170/170 after PR3; +41 new, 0 regressions)
- **Total tests passing (backend, full suite)**: unchanged at 160/160 — zero backend files touched, confirmed by `git diff --stat` scoped to `backend/`
- **Layers used**: Unit (backend-fetch, api-error, actions — 22 new), Integration/Route (id-route — 4 new), Component (product-form, id-page, products-page — 14 new, RTL + `userEvent`), Conformance (catalog-route — 3 new)
- **Approval tests**: None
- **Pure functions created**: 1 (`extractAdminError`) — everything else in this batch does I/O (fetch relay, DOM rendering) or Server Action RPC

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd frontend && npx vitest run src/lib/admin/__tests__/backend-fetch.test.ts src/lib/admin/__tests__/api-error.test.ts "src/app/(admin)/admin/products/actions.test.ts" "src/app/(admin)/admin/products/product-form.test.tsx" "src/app/(admin)/admin/products/[id]/page.test.tsx" "src/app/(admin)/admin/products/page.test.tsx" "src/app/api/admin/products/[id]/__tests__/route.test.ts" src/lib/pwa/__tests__/catalog-route-conformance.test.ts` → **41 passed** (all new/modified test files for this batch) |
| Runtime harness command/scenario and exact result | `npm run build` (webpack production build): Next compiled successfully, service worker bundled, and every new route (`/admin/products/new`, `/admin/products/[id]`, `/api/admin/products/[id]`) was picked up by Next's route manifest without a build-time route-resolution error. TypeScript's full-project type-check step in the SAME build surfaced 5 PRE-EXISTING errors in `src/proxy.test.ts` (an `admin-panel-auth`-era file, last touched in commit `1ae5d52`, never part of this PR's scope) — verified genuinely pre-existing by `git stash -u`-ing every PR4 file and re-running `tsc --noEmit`: the identical 5 errors reproduce with ZERO PR4 code present. Flagged as an out-of-scope, pre-existing build blocker in Issues Found below, not silently fixed |
| Rollback boundary | Revert every new/modified file listed above under `frontend/src/app/(admin)/admin/products/**`, `frontend/src/app/api/admin/products/**`, `frontend/src/lib/admin/backend-fetch.ts`, `frontend/src/lib/admin/api-error.ts`, and the `catalog-route-conformance.test.ts` extension. PR1/PR2/PR3 (backend) stay valid and green standalone — zero backend files touched, confirmed by `git diff --stat -- backend/` showing no output |

## Diff Size (measured, `git diff --cached --stat` with intent-to-add for new files)

17 files changed, 1788 insertions(+), 57 deletions(-) — **1845 authored
changed lines**. This is well past `tasks.md`'s own ~550-line estimate for
this work unit (tasks.md itself flagged this as a real possibility: "if
apply overruns, split into helper+actions / pages+form sub-PRs — flagged,
not forced now") and past the 400-line review budget on its own, following
the exact same pattern as PR1–PR3. Reported honestly, not trimmed. Driven
primarily by test volume under Strict TDD: the 8 new/modified test files
account for ~1053 of the 1845 lines; production code (`backend-fetch.ts`,
`api-error.ts`, `[id]/route.ts`, `actions.ts`, `product-form.tsx`,
`new/page.tsx`, `[id]/page.tsx`, `page.tsx`'s diff, `route.ts`'s diff, and
the conformance-test extension) totals **~792 lines**. This PR was already
flagged `400-line budget risk: High` with `stacked-to-main` chaining
pre-approved at the top-level Review Workload Forecast, so no further
chaining decision was needed to proceed with this slice as one PR; it
remains its own reviewable, autonomous unit. A further helper+actions /
pages+form split (as `tasks.md` flagged as a possibility) was considered
but not applied — the four low-level primitives (`backend-fetch`,
`api-error`, `[id]/route`, `actions`) are small and interdependent enough
that splitting them from the two components that consume them
(`product-form`, the pages) would create an inherently non-functional
intermediate PR (a page that renders a form with no action to wire it to).

## Deviations from Design

1. **`[id]/route.ts` originally proxied the LIST endpoint and filtered
   server-side — RESOLVED, now relays a real backend `GET {id}` route**
   (tasks 4.4/4.5): design.md's File Changes table listed a backend
   `GET {id}` route in `admin.py`'s one-line summary, but design.md's own
   Interfaces/Contracts section never specified its request/response
   shape (unlike `POST`/`PATCH`/both `DELETE`s), and it was missed from
   `tasks.md`'s Phase 3 breakdown entirely — the ACTUAL merged PR3
   `backend/src/gcell/api/admin.py` never implemented one. Sub-agent
   escalated this clearly rather than silently patching (worked around it
   with a list-and-filter relay); orchestrator reviewed the finding,
   confirmed with the user, and closed the gap properly: added
   `GET /admin/products/{product_id}` to `admin.py` (reuses `get_by_id`,
   unchanged since PR1, already excludes soft-deleted rows — zero
   repository/domain changes needed), with 2 new backend tests (200, 404),
   then rewrote `[id]/route.ts` to relay directly to it and updated its
   test to match. Also caught and fixed a real pre-existing TypeScript
   type error in `proxy.test.ts` (introduced during the earlier
   `admin-panel-auth` follow-up session, not this PR) that `npm test`/
   `npm run lint` didn't surface but `npm run build`'s `tsc` step did —
   confirmed clean via `npx tsc --noEmit` and a full `npm run build`
   afterward. Final state: 163/163 backend + 211/211 frontend tests,
   `tsc --noEmit` clean, production build succeeds with all new routes
   registered.
2. **`products/page.tsx` restructured to one row per PRODUCT, not per
   variant** (task 4.14): the pre-existing PR2/PR3-era page used
   `products.flatMap(product => product.variants.map(...))`, which renders
   ZERO rows for a product with an empty `variants` array — silently
   violating this change's own spec requirement "A Product May Have Zero
   Active Variants Without Being Retired... the product row MUST remain
   active and MUST still appear in the admin product list, editable, with
   zero variants." Since task 4.14 already required modifying this file
   for the New/Edit/Retire controls, this latent gap was fixed in the same
   pass rather than left in place or silently ignored — each product now
   renders exactly one row (with a nested variant list, or "No variants"),
   and the New/Edit/Retire controls attach at the product level, matching
   how the domain and the backend's own `AdminProductResponse` are
   actually shaped (one product, N variants nested inside).
3. **`retireVariantAction` invoked directly, not via `<form action>`**
   (task 4.10/4.11): design.md's Testing Strategy row for
   `product-form.tsx` says "removing a saved row submits the retire
   action" without specifying the invocation mechanism. Implemented as a
   direct call (`await retireVariantAction(formData)` inside a
   `useTransition`) rather than a nested `<form action={retireVariantAction}>`
   per row, because Next's Server Actions are plain async functions
   callable from client code — this lets the row's `useState` be updated
   locally the moment the retire resolves, which a raw form submission
   (whose only feedback loop is an implicit page-level refresh that does
   NOT reliably reset an already-mounted client component's internal
   state) cannot guarantee. `productId` gates this path: on the create
   page (no `productId` yet), every row is by definition unsaved, so this
   path is never reached there.

None of these deviations change any spec-level behavior; every
`admin-product-management` requirement and scenario this PR's scope covers
is satisfied exactly as written.

## Issues Found

1. **`npm run build`'s TypeScript step fails on 5 PRE-EXISTING errors in
   `src/proxy.test.ts`** — NOT introduced by this batch. Verified via
   `git stash -u` (stashing every PR4 file, tracked and untracked) followed
   by `npx tsc --noEmit`: the identical 5 errors (`TS2554`/`TS2345`/`TS7006`,
   all about a mocked function being called with 2 arguments against a
   0-argument mock type) reproduce with zero PR4 code present. This file
   was last touched in commit `1ae5d52` ("test(frontend): cover proxy.ts
   auth-gate branching logic"), an `admin-panel-auth`-era commit entirely
   outside this PR's scope (`proxy.ts` is explicitly not part of Phase 4's
   file list). `npm test` (vitest) and `npm run lint` (eslint) both stay
   fully green because neither runs a full-project `tsc` pass — this
   latent break only surfaces under `next build`'s dedicated type-check
   step, which this session appears to be the first to run end-to-end on
   this branch lineage. Not fixed here: touching `proxy.ts`/`proxy.test.ts`
   is out of this PR's explicit scope and risks scope creep into
   `admin-panel-auth`'s already-merged, already-reviewed territory.
   Flagged for a follow-up fix, not silently patched.
2. **`[id]/route.ts` refetches the full product list on every edit-page
   load** (see Deviation 1) — acceptable for the admin tool's expected
   scale (an internal catalog, not a public storefront), but not O(1).
   Worth revisiting if a real backend `GET /admin/products/{id}` route is
   ever added.

## Remaining Tasks (out of scope for PR4)

- [ ] Phase 5: Final Verification / Cleanup (manual E2E pass, no-restore/
      no-filter confirmation, full-repo regression, README note)

## Status (PR4)

16/16 Phase 4 tasks complete. Full frontend suite 211/211 (was 170/170
after PR3; +41 new, 0 regressions). Full backend suite unchanged at
160/160 (zero backend files touched). `npm run lint` clean. `npm run build`
compiles all new routes successfully; its TypeScript step surfaces 5
pre-existing, out-of-scope errors in `proxy.test.ts` (see Issues Found),
not a PR4 regression. Ready for `sdd-verify` on this PR4 slice. This
closes the last PR in the `admin-product-crud` chain (PR1→PR2→PR3→PR4,
`stacked-to-main`); Phase 5 (final verification/cleanup) remains for a
follow-up pass.

## Batch 3 (PR3 — API Routes)

**Scope**: Phase 3 (3.1–3.13), the pre-resolved "PR 3" work unit (`chain
strategy: stacked-to-main`, `delivery strategy: ask-on-risk`) from
`tasks.md`'s Review Workload Forecast. Branch
`pr3-product-crud-api-routes` off `main` (`7223970`, which already has
PR1's migration + read filters and PR2's port/adapters/use cases/slug
generation merged). No `create_product.py`/`update_product.py`/
`retire_product.py`/repository port/either adapter modified — this PR only
wires routes to PR2's use cases. No frontend files touched, per scope.
**Mode**: Strict TDD.

### Completed Tasks

- [x] 3.1 RED `test_admin.py` (extend): no token on write routes → `401`, repository never called
- [x] 3.2 RED same file: valid token + no pool → `503`, repository not invoked
- [x] 3.3 RED same file: `slug` in body → `422` (`extra="forbid"`)
- [x] 3.4 RED same file: valid `POST` → `201` with server-generated `slug`
- [x] 3.5 RED same file: `PATCH`/`DELETE` on unknown/retired id → `404`
- [x] 3.6 RED same file: IDOR across parents — cross-parent variant `DELETE` → `404`, never `403`
- [x] 3.7 GREEN `admin.py`: `AdminVariantInput`, `AdminProductWriteRequest`, request models
- [x] 3.8 GREEN `admin.py`: `POST /admin/products` → `CreateProductUseCase`, `201`
- [x] 3.9 GREEN `admin.py`: `PATCH /admin/products/{id}` → `UpdateProductUseCase`, `200`
- [x] 3.10 GREEN `admin.py`: `DELETE /admin/products/{id}` → `RetireProductUseCase`, `204`
- [x] 3.11 GREEN `admin.py`: `DELETE /admin/products/{id}/variants/{variant_id}` → `RetireVariantUseCase`, `204`
- [x] 3.12 GREEN `admin.py`: exception-to-status mapping (`422`/`404`/`409`)
- [x] 3.13 Regression: `test_health.py`, `test_lifespan.py` unmodified, stay green

## Files Changed (Batch 3)

| File | Action | What Was Done |
|---|---|---|
| `backend/src/gcell/api/admin.py` | Modified | Added `AdminVariantInput`/`AdminProductWriteRequest` request models (`extra="forbid"`, `Decimal` price/cost); `_execute_or_raise` helper (single exception-to-status mapping site for all 4 write routes); `POST /admin/products` (`201`, `CreateProductUseCase`); `PATCH /admin/products/{id}` (`200`, `UpdateProductUseCase`); `DELETE /admin/products/{id}` (`204`, `RetireProductUseCase`); `DELETE /admin/products/{id}/variants/{variant_id}` (`204`, `RetireVariantUseCase`) — every write route goes through a PR2 use case, never a repository method directly |
| `backend/tests/integration/api/test_admin.py` | Modified | +15 tests: 401/503 parametrized across all 4 write routes (8 tests), `slug`-in-body 422 for POST+PATCH (2), server-generated-slug 201 (1), 404 for unknown/retired product/variant (3), and the cross-parent IDOR test (1) using the real `db_pool` fixture + two products created via the real `CreateProductUseCase` |
| `openspec/changes/admin-product-crud/tasks.md` | Modified | Phase 3 tasks (3.1–3.13) marked `[x]` with DONE notes |

## TDD Cycle Evidence (Strict TDD Mode, Batch 3)

| Task | Test | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|------|-------|------------|-----|-------|-------------|----------|
| 3.1 | `test_no_token_on_write_routes_returns_401_and_never_calls_repository` | Integration (`TestClient`) | Pre-existing 3/3 GET tests in this file stayed green | Written and run: all 4 parametrized cases FAILED with `404 Not Found` (routes didn't exist) | 4/4 passed after wiring all 4 routes | 4 cases: POST/PATCH/DELETE-product/DELETE-variant | Clean |
| 3.2 | `test_valid_token_with_no_pool_returns_503_on_write_routes` | Integration (`TestClient`) | Same as above | Written and run: all 4 FAILED (`404`) | 4/4 passed | 4 cases, same route set | Clean |
| 3.3 | `test_slug_in_write_body_is_rejected_with_422` | Integration (`TestClient`) | Same | Written and run: both (POST/PATCH) FAILED (`404`) | 2/2 passed once `extra="forbid"` landed | 2 cases: POST, PATCH | Clean |
| 3.4 | `test_valid_post_creates_product_with_server_generated_slug` | Integration (`TestClient`, monkeypatched repo) | Same | Written and run: FAILED (`404`) | Passed once `POST` wired to `CreateProductUseCase` | 1 case (slug derivation is already exhaustively table-tested in PR2's `test_slug.py`; this test proves only the wiring) | Clean |
| 3.5 | 3 tests (patch/delete-product/delete-variant unknown-id) | Integration (`TestClient`, monkeypatched repo) | Same | Written and run: all 3 FAILED (`404` route-not-found, not yet the intended `404 not_found`) | 3/3 passed once the exception mapping landed | 3 distinct error sources: `UpdateProductUseCase`'s own `get_by_id` pre-check, `soft_delete`, `soft_delete_variant` | Clean |
| 3.6 | `test_delete_variant_cross_parent_returns_404_not_403` | Integration (`TestClient` + real `db_pool`) | Same | Written and run: FAILED (`404` route-not-found — proves nothing yet, since no route means everything 404s; the SUBSTANTIVE proof is described below) | Passed once the route called `RetireVariantUseCase` → `repository.soft_delete_variant`, whose SQL scopes `WHERE id = $1 AND product_id = $2` | 1 case, deliberately not parametrized — this is `design.md`'s single highest-value threat-matrix case, and design.md flagged it as needing its own careful test | Clean |
| 3.7–3.12 | (exercised via 3.1–3.6's tests) | N/A — no dedicated test file; these are the GREEN implementation tasks for 3.1–3.6's RED tests | N/A | N/A | Verified by the RED→GREEN transitions above | N/A | Clean |

### A note on 3.6's "genuine RED" requirement

Because no route existed before this batch, EVERY new test's initial run failed with a generic FastAPI `404 Not Found` (route-not-found), not the specific assertion failure it was designed to catch. This is still a legitimate RED — `pytest` genuinely failed before any production code existed — but for 3.6 specifically, a route-not-found `404` and the intended "cross-parent variant retire returns `404`" assertion happen to share the same status code, so the status-code assertion alone would not have distinguished "no route" from "route exists and correctly rejects." The RED run was verified by inspecting the actual failure: `response.json() == {"detail": "not_found"}` failed with `{'detail': 'Not Found'}` (FastAPI's default 404 body, capital N, no underscore) vs. the expected `{'detail': 'not_found'}` (this route's own body) — a byte-level difference that proves the RED run really did hit "no route" and not an accidental early-pass. After GREEN, the same assertion passes because the route now exists and returns its own generic body. The additional post-assertion (`still_active.variants` still contains `variant_b_id`) further proves no mutation occurred, which a route-not-found response could not have proven either way.

### Test Summary (Batch 3)
- **Total tests written this batch**: 15 (8 + 2 + 1 + 3 + 1 across the 6 test functions, parametrization counted individually)
- **Total tests passing (backend, full suite, `DB_URL` set, no filter)**: 160/160 (was 145/145 after PR2; +15 new, 0 regressions)
- **Total tests passing (frontend, full suite, no filter)**: 170/170 — identical to PR1/PR2's baseline, confirms zero frontend files touched
- **Layers used**: Integration only (`TestClient`, 14 with monkeypatched-spy `PostgresProductRepository` + 1 with the real local Postgres via `db_pool`)
- **Approval tests**: None
- **Pure functions created**: None — `_to_domain_variants` and `_execute_or_raise` are the only new functions; `_execute_or_raise` has I/O (awaits the wrapped coroutine)

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest tests/integration/api/test_admin.py -v` → **18 passed** (3 pre-existing GET + 15 new) |
| Runtime harness command/scenario and exact result | `tests/integration/api/test_admin.py::test_delete_variant_cross_parent_returns_404_not_403` runs a REAL `uvicorn`-equivalent request path: `TestClient`'s own ASGI lifespan opens a real `asyncpg` pool against the local Supabase Postgres, two products are persisted for real via `CreateProductUseCase`, the `DELETE` request is dispatched through the full FastAPI stack (auth → pool guard → route → `RetireVariantUseCase` → `PostgresProductRepository.soft_delete_variant`'s real SQL), and cleanup runs in `finally`. This is the closest equivalent to `tasks.md`'s suggested `curl` harness without needing a separately running server process |
| Rollback boundary | Revert the new routes, request models, and `_execute_or_raise`/`_to_domain_variants` helpers in `admin.py`, and the 15 new tests in `test_admin.py`. PR1 and PR2 stay valid and green standalone — nothing in this batch touches PR1/PR2's files |

## Diff Size (measured, `git diff --stat`)

2 files changed, 435 insertions(+), 7 deletions(-) — **442 authored changed
lines**. This is above `tasks.md`'s own ~300-line estimate for this work
unit, driven by the same pattern as PR1/PR2: the 15 new integration tests
(including the deliberately careful, heavily-commented IDOR test) account
for ~289 of the 442 lines, and the production code (`admin.py`'s diff)
totals ~153 lines. Reported honestly, not trimmed. This PR was already
flagged `400-line budget risk: High` with `stacked-to-main` chaining
pre-approved at the top-level Review Workload Forecast, so no further
chaining decision is needed for this slice; it remains its own reviewable,
autonomous PR.

## Deviations from Design

1. **Task text said `soft_delete`/`soft_delete_variant`, implementation
   calls `RetireProductUseCase`/`RetireVariantUseCase`** (tasks 3.10/3.11):
   `tasks.md`'s literal task text names the repository methods, but the
   user's explicit brief for this batch (reinforced by PR2's own
   `apply-progress.md` "Issues Found") requires routes to call the PR2 USE
   CASES, never `PostgresProductRepository` methods directly — the
   IDOR-adjacent guard for `update` lives at the use-case layer, and
   consistency (every write route going through its matching use case)
   was chosen over a route-by-route mix of "sometimes use case, sometimes
   repository directly." `RetireProductUseCase`/`RetireVariantUseCase` are
   both thin delegations to the exact same repository methods `tasks.md`
   named, so behavior is unchanged — only the call path is one layer
   higher, matching `CreateProductUseCase`/`UpdateProductUseCase`'s
   pattern for the other two routes.
2. **3.6's test uses `db_pool`, not `db_conn`** (design.md's Testing
   Strategy table doesn't specify which DB fixture to use for route-level
   integration tests): `db_conn` holds an open transaction on a connection
   bound to pytest's own event loop; `TestClient` drives the ASGI app's
   real ASGI lifespan (and therefore any `pool.acquire()` calls inside the
   route) on its OWN event loop via a background-thread portal. Reusing a
   `db_conn`-held connection across that loop boundary would raise
   asyncpg's "attached to a different loop" error. `db_pool` sidesteps
   this: connections are acquired and released per use, never held open
   across the boundary, and the two test products are committed for real
   and explicitly cleaned up in `finally` (no rows are left behind on
   either pass or failure, since the `finally` block runs regardless).
3. **No global FastAPI exception handlers** (design.md doesn't specify the
   mechanism, only the mapping table): implemented as a single
   `_execute_or_raise(operation: Awaitable[T]) -> T` helper that every
   write route wraps its use-case coroutine in, rather than
   `@app.exception_handler(...)` registrations on `main.py`. `admin.py`'s
   router has no access to the `FastAPI` app instance (composition-root
   pattern, `main.py` owns `app`), and a per-route wrapper keeps the
   mapping colocated with the routes it protects, visible in one file
   without needing to cross-reference `main.py`.

None of these deviations change any spec-level behavior; every
`admin-api-access` requirement and scenario is satisfied exactly as
written.

## Issues Found

None blocking. One confirmation worth flagging: `_execute_or_raise`
catches `(ValueError, TypeError)` broadly — this correctly covers every
domain invariant raised by `Product`/`ProductVariant.__post_init__` (via
`_to_domain_variants` or the use cases' own `Product(...)` construction),
but does NOT catch `UnslugifiableProductNameError` (raised by
`generate_unique_slug` inside `CreateProductUseCase` for a name with no
alphanumeric content) or `SlugGenerationExhaustedError` — neither is a
`ValueError`/`TypeError` subclass, and design.md's exception-to-status
table (task 3.12's exact scope) does not list them. An admin submitting a
name like `"🎁🎁"` would currently surface as an unhandled `500`, not the
`422` a caller would reasonably expect. This is a pre-existing gap in
design.md's mapping table, not something introduced by this batch — out
of this PR's explicit scope (task 3.12 says "per design.md's exact
table"), flagged here for a follow-up decision rather than silently
patched over the design's stated contract.

## Remaining Tasks (out of scope for PR3)

- [ ] Phase 4: Frontend (PR 4)
- [ ] Phase 5: Final Verification / Cleanup

## Status (PR3)

13/13 Phase 3 tasks complete. Full backend suite 160/160 (`DB_URL` set, no
filter, 0 regressions from PR2's 145). Full frontend suite 170/170
(unchanged from PR1/PR2's baseline, 0 files touched). Ready for
`sdd-verify` on this PR3 slice, then PR4 (`sdd-apply` Phase 4) targets this
branch per `stacked-to-main`.

## Batch 2 (PR2 — Port + Adapters + Slug)

**Scope**: Phase 2 (2.1–2.17), the pre-resolved "PR 2" work unit (`chain
strategy: stacked-to-main`, `delivery strategy: ask-on-risk`) from
`tasks.md`'s Review Workload Forecast. Branch
`pr2-product-crud-port-adapters-slug` off `main` (`26f92ba`, which already
has PR1's migration + read-filtered `PostgresProductRepository` merged). No
`api/admin.py` changes, no frontend — that scope is explicitly out for
PR3/PR4. Domain (`products/domain/product.py`) and `RegisterProductUseCase`
untouched, per design.md.
**Mode**: Strict TDD.

### Completed Tasks

- [x] 2.1 RED `test_slug.py`: `slugify` table-driven cases
- [x] 2.2 GREEN `slug.py`: `slugify`
- [x] 2.3 RED `test_slug.py`: `generate_unique_slug` collision scheme
- [x] 2.4 GREEN `slug.py`: `generate_unique_slug`
- [x] 2.5 GREEN `exceptions.py`: `ProductNotFoundError`, `VariantNotFoundError`, `UnslugifiableProductNameError`
- [x] 2.6 GREEN `repository.py`: 4 new Protocol methods
- [x] 2.7 GREEN `in_memory_product_repository.py`: 4 new methods + `_deleted` set
- [x] 2.8 RED `test_create_product_use_case.py`
- [x] 2.9 GREEN `create_product.py`
- [x] 2.10 RED `test_update_product_use_case.py`
- [x] 2.11 GREEN `update_product.py`
- [x] 2.12 RED `test_retire_product_use_case.py`
- [x] 2.13 GREEN `retire_product.py`
- [x] 2.14 RED `test_product_repository.py` (extend): adapter `update`/`slug_exists`/upsert-never-clears
- [x] 2.15 RED same file: ledger safety (product + variant retirement)
- [x] 2.16 GREEN `postgres_product_repository.py`: 4 new methods
- [x] 2.17 RED `test_catalog_soft_delete_views.py` (extend): port-method parity

## Files Changed (Batch 2)

| File | Action | What Was Done |
|---|---|---|
| `backend/src/gcell/products/application/slug.py` | Created | `slugify` (NFKD + combining-mark strip + lowercase + hyphen-collapse + 76-char truncation); `generate_unique_slug` (bounded 100-attempt `base`/`base-2`/... probe via `slug_exists`, 80-char overflow shortening); local `SlugGenerationExhaustedError` |
| `backend/src/gcell/products/application/exceptions.py` | Modified | Added `ProductNotFoundError`, `VariantNotFoundError`, `UnslugifiableProductNameError` |
| `backend/src/gcell/products/application/repository.py` | Modified | `ProductRepository` Protocol gains `update`, `soft_delete`, `soft_delete_variant`, `slug_exists`, docstrings copied verbatim from design.md's "Port additions" |
| `backend/src/gcell/products/application/create_product.py` | Created | `CreateProductUseCase` — derives slug via `generate_unique_slug`, delegates persistence to unmodified `RegisterProductUseCase` |
| `backend/src/gcell/products/application/update_product.py` | Created | `UpdateProductUseCase` — field edit + variant add/update in one `repository.update` call; slug frozen; cross-product variant ownership check via `repository.list_all()` scan → `VariantNotFoundError` |
| `backend/src/gcell/products/application/retire_product.py` | Created | `RetireProductUseCase`, `RetireVariantUseCase` — thin delegations to `soft_delete`/`soft_delete_variant`; no "≥1 active variant" invariant |
| `backend/src/gcell/products/infrastructure/in_memory_product_repository.py` | Modified | Implements the 4 new port methods; `_deleted: set[UUID]` mirror; `slug_exists` deliberately ignores `_deleted` |
| `backend/src/gcell/products/infrastructure/postgres_product_repository.py` | Modified | Implements `update` (one transaction, field `UPDATE` + per-variant `INSERT ... ON CONFLICT (id) DO UPDATE`, `deleted_at` never in either `SET` list), `soft_delete`, `soft_delete_variant` (both 0-rows-affected → the matching NotFound error), `slug_exists` (`deleted_at`-blind `EXISTS`) |
| `backend/tests/unit/products/test_slug.py` | Created | 10 tests: 4 table-driven `slugify` cases + truncation + emoji-only; 4 `generate_unique_slug` collision-scheme cases (first-bare, x3-suffixes, retired-slug-reserved, 100-attempt bound) |
| `backend/tests/unit/products/test_create_product_use_case.py` | Created | 3 tests: slug derivation, persistence round-trip, collision suffix |
| `backend/tests/unit/products/test_update_product_use_case.py` | Created | 6 tests: rename-preserves-slug, retired/unknown id → `ProductNotFoundError`, cross-product variant → `VariantNotFoundError`, new-variant-add, existing-variant-update |
| `backend/tests/unit/products/test_retire_product_use_case.py` | Created | 5 tests: product retirement, unknown-product error, sibling isolation, last-variant-succeeds (Q4), cross-product variant retire → `VariantNotFoundError` |
| `backend/tests/integration/db/test_product_repository.py` | Modified | +17 tests against real Postgres: `update` field/variant persistence, retired/unknown-id errors, mid-transaction-failure atomicity, `soft_delete`/`soft_delete_variant` (success + both NotFound paths), `slug_exists` (live/unknown/retired), upsert-never-resurrects-a-retired-variant, ledger-safety (product- and variant-level retirement) |
| `backend/tests/integration/db/test_catalog_soft_delete_views.py` | Modified | +2 parity tests: same view assertions as PR1's raw-SQL proof, now via `repository.soft_delete`/`soft_delete_variant` |
| `openspec/changes/admin-product-crud/tasks.md` | Modified | Phase 2 tasks (2.1–2.17) marked `[x]` with DONE notes |

## TDD Cycle Evidence (Strict TDD Mode, Batch 2)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 2.1/2.2 | `test_slug.py::TestSlugify` | Unit | Pre-existing 22/22 in `tests/unit/products/` stayed green | Written and run: `ModuleNotFoundError` (module didn't exist) | 6/6 passed after implementing `slugify` | 6 distinct cases (accents, symbols, whitespace-only, truncation, emoji-only) — full table from design.md | Clean, no further change needed |
| 2.3/2.4 | `test_slug.py::TestGenerateUniqueSlug` | Unit (in-memory repo) | 32/32 stayed green (after 2.7's adapter methods landed) | Written and run: `ModuleNotFoundError` | 4/4 passed after implementing `generate_unique_slug` | 4 cases: bare-slug, x3-suffix scheme, retired-slug-reservation, 100-attempt exhaustion | Clean |
| 2.6/2.7 | (exercised via 2.3/2.4 + 2.8–2.13's tests) | N/A — Protocol/adapter, no dedicated test file | N/A (structural additions) | N/A — pure structural port/adapter methods; triangulation skipped per Strict TDD's "purely structural" exception; correctness proven transitively by every downstream use-case test | Verified via downstream tests | N/A | Clean |
| 2.8/2.9 | `test_create_product_use_case.py` | Unit (in-memory repo) | 35/35 (post-2.4) stayed green | Written and run: `ModuleNotFoundError` | 3/3 passed | 3 cases: derivation, persistence, collision suffix | Clean |
| 2.10/2.11 | `test_update_product_use_case.py` | Unit (in-memory repo) | 38/38 stayed green | Written and run: `ModuleNotFoundError` | 6/6 passed | 6 cases incl. rename/slug-freeze, both NotFound paths, add vs. update | Clean |
| 2.12/2.13 | `test_retire_product_use_case.py` | Unit (in-memory repo) | 41/41 stayed green | Written and run: `ModuleNotFoundError` | 5/5 passed | 5 cases incl. Q4 last-variant-succeeds | Clean |
| 2.14/2.16 | `test_product_repository.py` (extend) | Integration (`db_conn`) | Pre-existing 11/11 in this file stayed green throughout | Written and run: 17 `AttributeError`/`Failed` (methods didn't exist / mid-tx test needed a real DB-only constraint) | 28/28 passed in the file after implementing `update`/`soft_delete`/`soft_delete_variant`/`slug_exists` | 17 distinct cases across all 4 methods | Clean — the mid-transaction test was corrected from a duplicate-id trick (silently absorbed by `ON CONFLICT DO UPDATE`) to a genuine `numeric(10,2)` overflow, documented below |
| 2.15 | `test_product_repository.py` (ledger safety) | Integration (`db_conn`) | Included in the 11/11 above | Written and run as part of the same 17 RED cases | 2/2 passed | 2 cases: product-level and variant-level retirement, both proving `count(*)`/`sum(quantity_delta)` invariance | Clean |
| 2.17 | `test_catalog_soft_delete_views.py` (extend) | Integration (`db_conn`) | Pre-existing 3/3 in this file stayed green | RED implicit: `soft_delete`/`soft_delete_variant` did not exist until 2.16 landed (proven earlier by 2.14's `AttributeError` runs against the same methods) | 5/5 passed in the file (3 original + 2 new parity tests) | 2 cases: product-level, single-variant-level parity with PR1's raw-SQL proof | Clean |

### Test Summary (Batch 2)
- **Total tests written this batch**: 43 (10 + 3 + 6 + 5 unit + 17 + 2 integration)
- **Total tests passing (backend, full suite, `DB_URL` set, no filter)**: 145/145 (was 102/102 after PR1; +43 new, 0 regressions)
- **Total tests passing (frontend, full suite, no filter)**: 170/170 — identical to PR1's baseline, confirms zero frontend files touched
- **Layers used**: Unit (24 new — `InMemoryProductRepository`-backed), Integration (19 new — real local Postgres via `db_conn`)
- **Approval tests**: None — no refactoring-of-existing-behavior tasks in this batch
- **Pure functions created**: 1 (`slugify`) — `generate_unique_slug` is not pure (repository I/O), by necessity

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest tests/unit/products/ tests/integration/db/test_product_repository.py -v` → **74 passed** |
| Runtime harness command/scenario and exact result | N/A — no HTTP route wires these use cases yet (that's PR3); per `tasks.md`'s own work-unit table, "unit + db-integration tests are the harness." Full db-integration confirmation: `DB_URL=... uv run pytest tests/integration/db/ -v` → **48 passed** (24 pre-existing + 5 view-parity + 19 repository-method tests) against the real local Postgres instance |
| Rollback boundary | Revert `slug.py`, the `repository.py` Protocol additions, both adapters' 4 new methods each, `create_product.py`/`update_product.py`/`retire_product.py`, and the two extended test files' new tests. PR1 (migration + read filters) stays valid and green standalone — nothing in this batch touches PR1's files beyond additive imports in the test files |

## Diff Size (measured, `git diff --stat` with intent-to-add for new files)

14 files changed, 1367 insertions(+), 16 deletions(-) — **1383 authored
changed lines**. This is well past `tasks.md`'s own ~450-line estimate for
this work unit and past the 400-line review budget on its own — reported
honestly per instructions, not trimmed to force a smaller number. The
overrun is driven almost entirely by test volume (43 new tests across 6
files, ~950 of the 1383 lines), which is expected and desired under Strict
TDD for a work unit implementing 4 new port methods across 2 adapters plus
3 new use cases plus a slug generator with an explicit collision-scheme
contract. Production code alone (`slug.py`, `exceptions.py`,
`repository.py`, `create_product.py`, `update_product.py`,
`retire_product.py`, and the two adapters' diffs) totals **~370 lines**,
close to the original estimate. This PR was already flagged
`400-line budget risk: High` with `stacked-to-main` chaining pre-approved,
so no further chaining decision is needed for this slice.

## Deviations from Design

1. **Task execution order** (2.3/2.4 vs. 2.5–2.7): `generate_unique_slug`'s
   tests need `InMemoryProductRepository.slug_exists` to exist to be
   meaningfully RED/GREEN-cyclable. Implemented 2.5 (exceptions), 2.6
   (Protocol), and 2.7 (in-memory adapter) ahead of 2.3/2.4's numeric
   position, then returned to complete `generate_unique_slug`. This is a
   dependency-order adjustment, not a scope change — all 17 tasks are
   still individually RED-then-GREEN and all marked complete.
2. **`update_product.py`'s cross-product variant check** (task 2.10/2.11):
   design.md specifies the repository `update` port's contract precisely
   but does not specify how the use case distinguishes "a genuinely new
   variant" from "a variant id belonging to a different product" (the
   `VariantNotFoundError` scenario explicitly required by the test
   coverage table). Implemented as a `repository.list_all()` ownership
   scan in the use case: a variant id owned by a different product raises
   `VariantNotFoundError`; an id owned by nobody is treated as a new
   addition. This keeps the IDOR guard at the use-case layer (Python),
   matching the Postgres `update`'s own contract (it only raises
   `ProductNotFoundError`, never `VariantNotFoundError`, per design.md's
   port docstring) — the DB-level `ON CONFLICT (id) DO UPDATE` has no
   product-scoping in its conflict target, so this check MUST happen
   before `repository.update` is ever called.
3. **Mid-transaction-failure test mechanism** (task 2.14): design.md's
   test-coverage table calls for "a mid-way failure leaves nothing
   changed" test, modeled on `add()`'s existing
   `test_failed_variant_insert_leaves_no_partial_rows` (a duplicate variant
   id within one call). For `update()`, that trick does not reproduce a
   failure: `ON CONFLICT (id) DO UPDATE` absorbs a duplicate id within the
   same call as a legitimate upsert, not an error. Used a genuine DB-only
   constraint instead — a `numeric(10,2)` magnitude overflow (a price the
   domain layer validates as finite/non-negative/2-decimal-places but
   whose value exceeds the column's total-digit precision) — to force a
   real, unavoidable `asyncpg.PostgresError` mid-transaction.
4. **`SlugGenerationExhaustedError` location**: design.md lists exactly 3
   new exceptions for `exceptions.py` (`ProductNotFoundError`,
   `VariantNotFoundError`, `UnslugifiableProductNameError`) and separately
   notes "100-attempt bound raises" without naming the exception. Defined
   `SlugGenerationExhaustedError` locally inside `slug.py` rather than
   adding a 4th class to `exceptions.py` — it is a slug-generation-specific
   failure mode, not a repository-port-contract error the way the other
   three are.

None of these deviations change any spec-level behavior; all 5
`product-persistence` spec requirements and their scenarios are satisfied
exactly as written.

## Issues Found

None blocking. One noteworthy confirmation: the `ON CONFLICT (id) DO
UPDATE` clause in `update()`'s variant upsert has no `product_id` in its
conflict target (matching design.md's literal SQL), which means the
Postgres adapter itself does not defend against a variant id belonging to
a different product — that guard lives entirely in `update_product.py`'s
use-case-level ownership check (Deviation 2 above). This is safe as
implemented (the use case is the only caller of `repository.update` in
this codebase), but is worth flagging explicitly for PR3: `api/admin.py`
must call `UpdateProductUseCase`, never `PostgresProductRepository.update`
directly, or the IDOR guard is bypassed.

## Remaining Tasks (out of scope for PR2)

- [ ] Phase 3: API Routes (PR 3)
- [ ] Phase 4: Frontend (PR 4)
- [ ] Phase 5: Final Verification / Cleanup

## Status (PR2)

17/17 Phase 2 tasks complete. Full backend suite 145/145 (`DB_URL` set, no
filter, 0 regressions from PR1's 102). Full frontend suite 170/170
(unchanged from PR1's baseline, 0 files touched). Ready for `sdd-verify` on
this PR2 slice, then PR3 (`sdd-apply` Phase 3) targets this branch per
`stacked-to-main`.

## Batch 1 (PR1 — Migration + Read Filters)

**Scope**: Phase 0 (0.1–0.2) + Phase 1 (1.1–1.6), the pre-resolved "PR 1"
work unit (`chain strategy: stacked-to-main`, `delivery strategy:
ask-on-risk`) from `tasks.md`'s Review Workload Forecast. Branch
`pr1-product-crud-migration-read-filters` off `main` (`f14ec39`). No port/
adapter method additions beyond the three existing SELECTs' read filters, no
API routes, no frontend — that scope is explicitly out for PR2–PR4.
**Mode**: Strict TDD.

### Completed Tasks

- [x] 0.1 Confirmed local Supabase stack up (`npx supabase status`) — core
      services (DB, Auth, REST, Studio) running
- [x] 0.2 Picked migration filename timestamp `20260811000000` (sorts after
      `20260810000502`, follows the repo's `YYYYMMDDHHMMSS_snake_case.sql`
      convention)
- [x] 1.1 Created `supabase/migrations/20260811000000_products_soft_delete.sql`
      — `deleted_at timestamptz` on `products` and `product_variants`
      (nullable, no default), `products_active_idx` and
      `product_variants_active_product_idx` partial indexes; applied via
      `npx supabase migration up`
- [x] 1.2 Same migration: `CREATE OR REPLACE VIEW` for `catalog_products`,
      `catalog_variants`, `catalog_product_images` — identical column
      lists/types/order to `20260810000458_public_catalog_rls.sql`, only a
      `WHERE ... deleted_at IS NULL` addition (cascade via
      `p.deleted_at IS NULL` on the variants/images views)
- [x] 1.3 RED `backend/tests/integration/db/test_product_repository.py`
      (extend) — the `ON`-vs-`WHERE` trap
- [x] 1.4 GREEN `backend/src/gcell/products/infrastructure/postgres_product_repository.py`
      — `deleted_at IS NULL` filters added
- [x] 1.5 RED (proven) + tests `backend/tests/integration/db/test_catalog_soft_delete_views.py`
      (new) — view-level soft-delete exclusion
- [x] 1.6 Regression — public-catalog frontend tests + full backend/frontend
      suites confirmed green, unmodified

## Files Changed

| File | Action | What Was Done |
|---|---|---|
| `supabase/migrations/20260811000000_products_soft_delete.sql` | Created | `deleted_at timestamptz` on `products`/`product_variants` (nullable, no default); `products_active_idx` (`created_at, id` where `deleted_at is null`); `product_variants_active_product_idx` (`product_id` where `deleted_at is null`); `CREATE OR REPLACE VIEW` for all 3 catalog views with an added `WHERE`/`ON`-cascade filter, identical column lists to the prior migration |
| `backend/src/gcell/products/infrastructure/postgres_product_repository.py` | Modified | `_SELECT_BY_SLUG`/`_SELECT_BY_ID`/`_SELECT_ALL`: added `p.deleted_at IS NULL` to each `WHERE`; added `AND v.deleted_at IS NULL` to each `LEFT JOIN product_variants v ON ...` — the variant filter is in `ON`, never `WHERE`, per design.md's explicit warning |
| `backend/tests/integration/db/test_product_repository.py` | Modified | Added `test_list_all_keeps_product_with_every_variant_retired` — the `ON`-vs-`WHERE` trap RED/GREEN test |
| `backend/tests/integration/db/test_catalog_soft_delete_views.py` | Created | 3 tests: product retirement removes it from all 3 catalog views (incl. hero + variant images); retiring one variant hides only that variant and its image while siblings/hero survive; a live untouched product is unaffected by a sibling's retirement |
| `openspec/changes/admin-product-crud/tasks.md` | Modified | Phase 0 + Phase 1 tasks marked `[x]` with DONE notes |

## TDD Cycle Evidence (Strict TDD Mode)

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.3/1.4 | `test_product_repository.py` | Integration (`db_conn`) | Pre-existing 10/10 tests in this file stayed green throughout | Written and run: FAILED — retired variant still returned in `fetched.variants` (adapter reads unfiltered rows pre-fix) | Passed 11/11 in the file after adding `deleted_at IS NULL` filters | N/A — single case is the entire threat (the `ON`-vs-`WHERE` degradation) | Clean, no further change needed |
| 1.5 | `test_catalog_soft_delete_views.py` | Integration (`db_conn`) | N/A (new file) | Proven via a separate, non-destructive proof: replayed the pre-migration view SQL inside a transaction rolled back at the end, confirmed a retired product's row still leaked through `catalog_products` under the OLD definitions | All 3 tests pass against the real, already-migrated view definitions | 3 distinct cases: full-product retirement, single-variant retirement (siblings + hero image survive), live-product non-interference | Clean |

### Test Summary
- **Total tests written this batch**: 4 new (1 repository trap test + 3 view tests)
- **Total tests passing (backend, full suite, no filter)**: 102/102
- **Total tests passing (frontend, full suite, no filter)**: 170/170 (30 files)
- **Layers used**: Integration only (this batch has no application/domain surface — read-side SQL filters only)
- **Approval tests**: None
- **Pure functions created**: None — pure SQL/adapter-filter change

## Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `cd backend && uv run pytest tests/integration/db/test_product_repository.py tests/integration/db/test_catalog_soft_delete_views.py -v` (with `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres`) → **14 passed** |
| Runtime harness command/scenario and exact result | `npx supabase migration up` against the real local Postgres → applied cleanly; verified via a direct `asyncpg` script: `deleted_at` present on both tables, both partial indexes present with the correct `WHERE` predicate, all 3 view column lists byte-identical to `frontend/src/lib/catalog/columns.ts`. Separately, RED proof for the view filter: replayed the pre-migration `CREATE OR REPLACE VIEW` definitions inside a transaction that was rolled back, confirmed a retired product row was NOT filtered under the old definitions, confirmed no lasting schema change after rollback |
| Rollback boundary | Revert `supabase/migrations/20260811000000_products_soft_delete.sql` (additive: `alter table ... drop column deleted_at` + re-run the two prior view definitions from `20260810000458_public_catalog_rls.sql`, per design.md's documented rollback) and the `WHERE`/`ON` diff in `postgres_product_repository.py`; delete `test_catalog_soft_delete_views.py` and the one added test in `test_product_repository.py`. No product, variant, image, or stock row is ever destroyed by the forward path |

## Diff Size (measured, `git diff --stat` with intent-to-add for new files)

4 files changed, 276 insertions(+), 5 deletions(-) — **281 authored changed
lines**, within the 400-line budget (`tasks.md`'s own estimate for this
work unit was `~200`; the 3-test view file plus the trap test's docstring
pushed it to 281, still comfortably under budget and the smallest of the
4 planned PR slices).

## Deviations from Design

None. The migration SQL is byte-for-byte design.md's "Migration (the only
view-safe shape)" block; the repository filter placement (`ON` for the
variant join, `WHERE` for the product row) matches design.md's explicit
"the `LEFT JOIN` filter goes in `ON`, never in `WHERE`" decision exactly.

## Issues Found

None. One design assumption was worth stress-testing rather than accepting
on faith: whether the `ON`-vs-`WHERE` trap would actually reproduce against
the pre-fix adapter. It did — task 1.3's RED run failed with the retired
variant still present in `fetched.variants`, confirming the adapter read
every row unfiltered before this batch, exactly as design.md predicted.

## Remaining Tasks (out of scope for PR1)

- [ ] Phase 2: Port + Adapters + Slug (PR 2)
- [ ] Phase 3: API Routes (PR 3)
- [ ] Phase 4: Frontend (PR 4)
- [ ] Phase 5: Final Verification / Cleanup

## Status (PR1)

8/8 Phase 0 + Phase 1 tasks complete (2 prerequisite + 6 implementation).
Ready for `sdd-verify` on this PR1 slice, then PR2 (`sdd-apply` Phase 2)
targets this branch per `stacked-to-main`.
