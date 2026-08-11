```yaml
schema: gentle-ai.verify-result/v1
evidence_revision: sha256:cb89731188745926ccf088033cce0477b32df8ebd3e144add44ea083d9dcd8b5
verdict: fail
blockers: 1
critical_findings: 1
requirements: 13/16
scenarios: 31/34
test_command: "cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest -q  &&  cd frontend && npm test -- --run"
test_exit_code: 0
test_output_hash: sha256:13d8e7c6a444b4d28177dcee92d262ae3e3ac526aa86cf6f0a3e0732a3e89e59
build_command: "cd frontend && npm run build"
build_exit_code: 0
build_output_hash: sha256:c4c35bb2955c643e211a7de7d6382d124e83d438ed8fe12cbb4c46eb9f80ff27
```

## Verification Report

**Change**: admin-product-crud
**Version**: N/A (initial implementation, 4 stacked PRs merged to main: 26f92ba (PR1), 7223970 (PR2), d6aef2e (PR3), 0dcdfd0 (PR4))
**Mode**: Strict TDD

This report independently re-verifies the change end-to-end against the real merged code on `main` (HEAD `0dcdfd0`), not against apply-progress.md's self-reported claims. Both real test suites were re-run in this session with `DB_URL` exported (required, or ~24 DB-integration tests silently skip), `npx tsc --noEmit` was re-run standalone, and `npm run build` was re-run to reconfirm the production build and route table. One CRITICAL finding was discovered that apply-progress.md never surfaced: the `product-persistence` spec's literal text for `soft_delete`'s product-to-variant cascade is contradicted by the actual (and design.md-documented, deliberately different) implementation.

### Completeness

| Metric | Value |
|--------|-------|
| Tasks total (Phases 0-5) | 59 |
| Tasks complete | 54 |
| Tasks incomplete | 5 (all Phase 5: 5.1 manual E2E pass, 5.2 no-restore confirmation, 5.3 no-filter confirmation, 5.4 full regression, 5.5 README doc) |
| Phases 0-4 (code-bearing) | 54/54 complete, matches tasks.md's on-disk checked state exactly |
| Phase 5 (final verification/cleanup) | 0/5 checked in tasks.md, but 5.2/5.3 (no restore, no filter) and 5.4 (full regression) were independently re-proven in this verification session (see Correctness and Build & Tests sections) -- only 5.1 (a documented manual E2E click-through) and 5.5 (README note) remain genuinely undone |

### Build & Tests Execution

**Backend**: PASSED (re-run with DB_URL exported, no filter)
```text
$ cd backend && DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run pytest -q
163 passed, 1 warning in 2.26s
```
163/163 exactly matches apply-progress.md's final claimed count ("163/163 backend"). Re-confirmed independently, not trusted.

**Frontend**: PASSED
```text
$ cd frontend && npm test -- --run
Test Files  36 passed (36)
     Tests  211 passed (211)
```
211/211 exactly matches apply-progress.md's claimed count ("211/211, was 170/170 after PR3; +41 new, 0 regressions").

**Type-check**: `npx tsc --noEmit` (frontend) -- re-run standalone this session, zero output, exit 0. Confirms the pre-existing proxy.test.ts TypeScript bug (5 errors: TS2554/TS2345/TS7006) that PR4's apply session found and fixed is genuinely fixed on main, not just claimed.

**Build**: `npm run build` -- re-run this session. Compiled successfully, Finished TypeScript (the same full-project tsc pass next build runs) with zero errors, all routes registered including the 3 new ones (/admin/products/new, /admin/products/[id], /api/admin/products/[id]), service worker bundled.

**Lint**: Not re-run this session (not requested); apply-progress.md claims clean, not independently re-verified here.

**Coverage**: Not measured -- informational only, not blocking.

### Spec Compliance Matrix

**admin-product-management** (7 requirements / 12 scenarios)

| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Product Creation Form Validates And Persists With A Server-Generated Slug | Valid submission creates a product with a generated slug | test_admin.py::test_valid_post_creates_product_with_server_generated_slug + actions.test.ts (201->redirect) | COMPLIANT |
| same | Invalid submission shows feedback and does not persist | actions.test.ts (422->{error}, no redirect) + product-form.test.tsx (role="alert") | COMPLIANT |
| same | Same name across two creations yields distinct slugs | test_slug.py (collision-scheme cases) + test_create_product_use_case.py (collision suffix) | COMPLIANT |
| Product Edit Persists Field And Variant Changes Atomically | Field and variant changes persist together | test_update_product_use_case.py + test_product_repository.py (update integration, mid-tx-failure atomicity) | COMPLIANT |
| same | Slug never changes after creation, even on rename | test_update_product_use_case.py::rename-preserves-slug (explicit assert) + product-form.tsx renders no slug field (confirmed by direct read; no dedicated negative-assertion test) | COMPLIANT |
| Soft-Deleting A Product Cascades To Hide Its Variants | Disappears from the admin list | test_list_all_keeps_product_with_every_variant_retired (ON-vs-WHERE trap, inverse case) + test_catalog_soft_delete_views.py + page.test.tsx | COMPLIANT |
| same | Disappears from the public catalog | test_retiring_a_product_removes_it_from_all_three_catalog_views (and its port-method-parity twin) | COMPLIANT |
| same | Soft-deleting a product hides all of its variants | Same test -- asserts catalog_variants excludes the retired product's variants | COMPLIANT |
| A Variant Can Be Retired Independently Of Its Product | Retiring one variant leaves the product and siblings active | test_soft_delete_variant_retires_only_that_variant + test_retiring_one_variant_hides_only_that_variant_and_its_image + product-form.test.tsx (remove-saved-row) | COMPLIANT |
| A Product May Have Zero Active Variants Without Being Retired | Removing the last variant leaves the product editable | test_retire_product_use_case.py (last-variant-succeeds, Q4) + page.test.tsx (zero-variant product still listed) | COMPLIANT |
| No Restore Capability In This Change | No restore control exists | Static: read product-form.tsx, page.tsx, actions.ts in full -- no restore/undo action defined anywhere; grep for restore/Restore across admin/products/** returns zero matches. No runtime test asserts this negative | PARTIAL -- static evidence only, no covering runtime test |
| No "Show Retired" Filter -- Soft-Deleted Rows Are Hidden Entirely | Soft-deleted rows never reappear via a filter or toggle | Static: no filter/toggle control exists in page.tsx; all reads go through ProductRepository methods that unconditionally filter deleted_at IS NULL. No runtime test asserts the negative UI claim | PARTIAL -- static evidence only, no covering runtime test |

**admin-api-access** (1 requirement / 7 scenarios) -- all re-verified via the real, passing backend suite:

| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Product Read And Write Endpoints | Authenticated GET request returns product data | pre-existing test_admin.py GET test (unmodified, still green) | COMPLIANT |
| same | Unauthenticated GET never reaches the repository | pre-existing test_admin.py GET test | COMPLIANT |
| same | Authenticated GET by id returns one product or 404 | test_get_single_admin_product_returns_200 + test_get_single_admin_product_unknown_or_retired_returns_404 -- both real, added post-PR3 by the orchestrator to close the exact gap this spec scenario names | COMPLIANT |
| same | Authenticated POST creates a product | test_valid_post_creates_product_with_server_generated_slug | COMPLIANT |
| same | Authenticated PATCH and DELETE reach their handlers | test_patch_unknown_or_retired_product_returns_404, test_delete_product_unknown_or_retired_returns_404, test_delete_variant_unknown_or_retired_returns_404 (each proves the route calls its use case, since a 404 only reaches this shape via the use case's own not-found path) | COMPLIANT |
| same | Unauthenticated write request rejected before DB pool guard or handler | test_no_token_on_write_routes_returns_401_and_never_calls_repository (parametrized over all 4 write routes, spy proves repository never called) | COMPLIANT |
| same | Authenticated write request with unavailable DB pool fails with 503 | test_valid_token_with_no_pool_returns_503_on_write_routes (same 4-route parametrization) | COMPLIANT |

**product-catalog-schema** (3 requirements / 6 scenarios) -- all COMPLIANT:

| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Soft-Delete Column On Products And Variants | Soft-deleting a product marks it without removing the row | test_soft_delete_retires_the_product_via_update (asserts row still present, deleted_at set) | COMPLIANT |
| same | Soft-deleting a variant marks it without removing the row | test_soft_delete_variant_retires_only_that_variant | COMPLIANT |
| Public Catalog Views Exclude Soft-Deleted Rows | Soft-deleted product never appears in a public catalog read | test_retiring_a_product_removes_it_from_all_three_catalog_views | COMPLIANT |
| same | Soft-deleted variant never appears in a public catalog read | test_retiring_one_variant_hides_only_that_variant_and_its_image | COMPLIANT |
| Soft-Delete Never Touches stock_movements | Soft-deleting a variant with recorded stock movements leaves the ledger intact | ledger-safety tests in test_product_repository.py (count/sum invariance on stock_movements, product- and variant-level) | COMPLIANT |
| same | FK RESTRICT and append-only trigger stay unexercised | Same ledger-safety tests (no error raised) + static: grep -rn stock_movements src/gcell/ shows zero UPDATE/DELETE against that table anywhere outside the pre-existing, untouched stock module | COMPLIANT |

**product-persistence** (5 requirements / 9 scenarios):

| Requirement | Scenario | Test | Result |
|---|---|---|---|
| Repository Create Persists Product With Variants | Create with variants and no stock | pre-existing test_product_repository.py add() tests (unmodified, still green) | COMPLIANT |
| same | Create returns generated ids | Same | COMPLIANT |
| Duplicate Slug Is Rejected On Registration | Same name yields distinct slugs, not a rejection | test_slug.py collision cases + test_create_product_use_case.py | COMPLIANT |
| same | A true duplicate slug is still rejected at the database | test_duplicate_slug_raises_duplicate_product_slug_error + test_duplicate_slug_leaves_no_new_product_row | COMPLIANT |
| Slug Is Immutable After Creation | Renaming a product does not change its slug | test_update_product_use_case.py::rename-preserves-slug + integration update() test asserting persisted slug unchanged | COMPLIANT |
| Repository Update Persists Field And Variant Changes Atomically | Field and variant changes commit together | test_product_repository.py update() integration tests | COMPLIANT |
| same | A failed update leaves no partial change | test_product_repository.py mid-transaction-failure test (numeric overflow constraint) | COMPLIANT |
| Repository Soft-Delete Retires A Product Or Variant Without Row Deletion | Soft-deleting a product cascades to its variants | NONE -- and the literal claim is FALSE against the real code. postgres_product_repository.py::soft_delete() issues exactly one `UPDATE products SET deleted_at = now() WHERE id = $1` and never touches product_variants; in_memory_product_repository.py's soft_delete() adds only the product id to a _deleted set, never marks any variant. test_soft_delete_retires_the_product_via_update (the only soft_delete-product test in the suite) asserts ONLY the product row's deleted_at, never the variant rows'. A test asserting "both variant rows MUST be marked retired via UPDATE" (the spec's literal words) would fail against the current implementation. | FAILING -- spec text contradicted by design.md's deliberate, documented decision, never reconciled back into spec.md |
| same | Soft-deleting a single variant does not affect the product or siblings | test_soft_delete_variant_retires_only_that_variant | COMPLIANT |

**Compliance summary**: 31/34 scenarios COMPLIANT with a re-runnable, passing automated test proving the exact literal claim. 2/34 (No Restore, No Show-Retired-Filter) are PARTIAL -- true by static/source-level evidence but have no runtime test asserting the negative. 1/34 is FAILING -- the product-persistence spec's literal "product row and both variant rows MUST be marked retired via UPDATE" is directly contradicted by the merged code's real SQL, and no test in the suite could pass if it asserted that literal claim.

### Correctness (Static Evidence) -- critical architectural/security properties, read and confirmed in full this session

| Property | Status | Notes |
|---|---|---|
| Variant LEFT JOIN filter lives in ON, never WHERE | Confirmed | postgres_product_repository.py lines 35/43/51: `LEFT JOIN product_variants v ON v.product_id = p.id AND v.deleted_at IS NULL`; `WHERE p.deleted_at IS NULL` filters only the product row |
| Every write route calls a PR2 use case, never the repository directly | Confirmed | admin.py -- all 4 write routes construct CreateProductUseCase/UpdateProductUseCase/RetireProductUseCase/RetireVariantUseCase; grep for PostgresProductRepository(conn).update/.soft_delete/.soft_delete_variant at route level returns zero matches -- only the two read routes (list_all, get_by_id) call the repository directly, which is correct (no IDOR guard needed for reads) |
| Retired slugs stay reserved | Confirmed | `_SLUG_EXISTS = "SELECT EXISTS(SELECT 1 FROM products WHERE slug = $1)"` -- no deleted_at filter, exactly as design.md specifies |
| stock_movements never touched by new code | Confirmed | grep -rn stock_movements backend/src/gcell/ -- every hit is either a comment/docstring or the pre-existing stock module's INSERT-only repository; zero UPDATE/DELETE against that table anywhere in the products module |
| No write Route Handler exists | Confirmed | Both frontend/src/app/api/admin/products/route.ts and [id]/route.ts export only GET; all 4 mutating operations live exclusively in actions.ts as "use server" Server Actions |
| Money precision preserved | Confirmed | grep -n "parseFloat/Number(" across actions.ts/product-form.tsx returns zero code hits (one doc-comment mention describing what NOT to do); buildVariantsPayload carries price/cost as String(...) of the raw FormData value |
| IDOR-across-parents test is real, not mocked | Confirmed | test_delete_variant_cross_parent_returns_404_not_403 creates two real products via CreateProductUseCase against the real local Postgres (db_pool fixture), dispatches a real TestClient request through the full stack, asserts 404/{"detail": "not_found"}, and re-fetches product B afterward to prove variant_b_id is untouched; explicit finally cleanup |
| products/domain/product.py untouched (design.md's explicit constraint) | Confirmed | git diff f14ec39 0dcdfd0 -- backend/src/gcell/products/domain/product.py -- empty diff across the entire 4-PR chain |
| Slug frozen on rename (product decision) | Confirmed | `_UPDATE_PRODUCT_FIELDS = "UPDATE products SET name = $2, model = $3 WHERE id = $1..."` -- no slug in the SET list; UpdateProductUseCase.execute always passes through existing.slug |
| No restore capability anywhere in the admin UI | Confirmed | Full read of product-form.tsx, page.tsx, [id]/page.tsx, actions.ts -- no restore/undo action defined; grep -rni "restore/undo" across admin/products/** returns zero matches |
| No "show retired" filter anywhere | Confirmed | Same files -- no filter/toggle state or query param; every list read is unconditionally pre-filtered server-side |
| Zero active variants without being retired | Confirmed | RetireVariantUseCase/both adapters' soft_delete_variant have no "at least one active variant" invariant anywhere; page.tsx was restructured (PR4 deviation) to render one row per product so a zero-variant product still lists |
| Product soft-delete hides variants (read-time cascade) vs. variant retires independently | Confirmed as designed, but see CRITICAL finding above | Cascade is implemented exactly as design.md claims (read-time join filter), but NOT as product-persistence spec.md claims (variant-row stamping) -- the two artifacts disagree and only one matches the code |

### Scope Leakage Check

| Check | Result | Evidence |
|---|---|---|
| products/domain/product.py untouched across all 4 PRs | Confirmed | git diff f14ec39 0dcdfd0 -- backend/src/gcell/products/domain/product.py -> empty |
| No write Route Handler introduced | Confirmed | Both route.ts files GET-only |
| lib/catalog/columns.ts / lib/pwa/runtime-caching.ts byte-untouched | Confirmed by apply-progress.md's SHA256-pin evidence (re-verified: catalog-route-conformance.test.ts's hash-pin test is part of the 211/211 passing frontend suite, would fail on any runtime-caching.ts byte change) | Indirect (pin-test proof, not a direct diff re-read this session) |
| Full diff scope | Confirmed | git diff f14ec39 0dcdfd0 --stat -> 38 files changed, 4628 insertions(+), 134 deletions(-), confined to backend/src/gcell/products/**, backend/src/gcell/api/admin.py, backend/tests/**, supabase/migrations/**, frontend/src/app/(admin)/admin/products/**, frontend/src/app/api/admin/products/**, frontend/src/lib/admin/**, frontend/src/lib/pwa/__tests__/catalog-route-conformance.test.ts (+the one unrelated pre-existing proxy.test.ts type-bug fix, and openspec/changes/admin-product-crud/** docs) |

### Coherence (Design)

| Decision | Followed? | Notes |
|---|---|---|
| deleted_at timestamptz NULL on both tables | Yes | Migration 20260811000000_products_soft_delete.sql matches design.md's SQL block (spot-checked column/index/view shapes) |
| Retired slugs stay reserved (global unique index kept) | Yes | slug_exists ignores deleted_at, confirmed above |
| Product retirement cascades at READ time, not by stamping variants | Yes -- followed exactly | This is the source of the CRITICAL finding above: design.md deliberately overrides product-persistence spec.md's literal text, and the code follows design.md, not spec.md. design.md's own "Open Questions" section reconciled one divergence (Server-Actions-only) explicitly but never mentions or reconciles this one |
| LEFT JOIN filter in ON, never WHERE | Yes | Confirmed above |
| Slug generated in application/, validated only by domain | Yes | slug.py confirmed; Product.__post_init__'s _SLUG_PATTERN untouched |
| PATCH never retires; retirement has its own URL | Yes | update_product.py never deletes a variant; UpdateProductUseCase reconciles by add/update only |
| 422 for every rejected body, no 400 | Yes | _execute_or_raise maps ValueError/TypeError/UnslugifiableProductNameError/SlugGenerationExhaustedError -> 422, not-found -> 404, duplicate slug -> 409 |
| No write Route Handlers -- Server Actions relay directly | Yes | Confirmed above; this design deviation from the original proposal was explicitly reconciled with the spec (design.md's Open Questions) |

### TDD Compliance (Strict TDD Mode)

| Check | Result | Details |
|---|---|---|
| TDD Evidence reported | Yes | All 4 batches in apply-progress.md have a full "TDD Cycle Evidence" table with RED/GREEN/TRIANGULATE/REFACTOR columns |
| All tasks have tests | Yes | Every task in Phases 1-4 names a specific test file, confirmed to exist on disk and pass in this session's re-run |
| RED confirmed | Yes (self-reported, consistent with code structure) | Not independently re-run this session (would require reverting commits); apply-progress.md's failure-mode descriptions (ModuleNotFoundError, specific assertion diffs) are consistent with genuine RED runs |
| GREEN confirmed | Yes | 163/163 backend + 211/211 frontend, re-run this session, exact match to claimed counts |
| Triangulation adequate | Yes | Multiple distinct cases per behavior throughout (e.g. slugify's 6-case table, IDOR's dedicated non-parametrized deep test) |
| Safety Net for modified files | Yes | Pre-existing route.test.ts, columns.test.ts, queries.test.ts, catalog-route-conformance.test.ts all confirmed unmodified and green as part of the 211/211 run |

### Assertion Quality

Sampled test_admin.py (IDOR test + 404/401/503 parametrized tests), test_product_repository.py (soft_delete/update tests), actions.ts/actions.test.ts, product-form.tsx/product-form.test.tsx in full this session. No tautologies, no assertion-free tests found. One notable gap (not a tautology, a coverage gap): test_soft_delete_retires_the_product_via_update only asserts the product row's deleted_at, never checking the variant rows -- this is the exact hole that let the CRITICAL spec/implementation divergence go undetected by the test suite itself.

**Assertion quality**: 0 tautologies found; 1 coverage gap directly enabling the CRITICAL finding.

### Issues Found

**CRITICAL**:
1. product-persistence spec's "Repository Soft-Delete Retires A Product Or Variant Without Row Deletion" requirement, scenario "Soft-deleting a product cascades to its variants," literally states: "the product row and both variant rows MUST be marked retired via UPDATE." The merged code (PostgresProductRepository.soft_delete, InMemoryProductRepository.soft_delete) does the opposite by design: it stamps only the product row and relies on every read joining deleted_at IS NULL to hide variants at read time -- exactly as design.md's "Decision: product retirement cascades at read time, not by stamping variants" explicitly and deliberately chose, for good stated reasons (a future restore couldn't otherwise distinguish "hidden because parent retired" from "retired individually"). The user-visible behavior is correct and well-tested (variants really do disappear from every admin/public read after a product retirement -- test_catalog_soft_delete_views.py proves this). The problem is purely that spec.md's literal text was never reconciled with design.md's deliberate override, unlike the Server-Actions-only divergence which design.md's Open Questions section explicitly closed. No test in the 163-test backend suite asserts the literal "both variant rows marked retired" claim (only the product row's deleted_at is checked), so this divergence would have shipped to sdd-archive silently. Recommend before archive: either (a) edit product-persistence/spec.md's requirement text and scenario to describe the read-time-cascade behavior actually implemented (matching design.md, and matching the already-correct admin-product-management spec, which only describes the observable effect -- "variants become hidden" -- not the mechanism), or (b) if row-stamping is genuinely required for a future restore feature, implement it and add the missing test. Given admin-product-management's spec is scenario-compatible with the current implementation and product decisions have no restore feature in scope, (a) is the low-risk fix.

**WARNING**: None.

**SUGGESTION**:
1. Add a runtime test that explicitly asserts the negative claims in "No Restore Capability In This Change" and "No Show-Retired Filter" (e.g. `expect(screen.queryByText(/restore/i)).not.toBeInTheDocument()` in page.test.tsx/product-form.test.tsx) -- currently these two scenarios are true only by omission (nothing was built), not by an assertion that would catch a future regression if a restore/filter control were accidentally added.
2. Complete Phase 5's two genuinely-remaining tasks before archive: 5.1 (one documented manual E2E click-through: create -> edit -> retire -> confirm gone from /admin/products and the public catalog -- no automated equivalent exists) and 5.5 (a short README note on the soft-delete behavior and the final migration filename, if project convention requires it). 5.2, 5.3, and 5.4 were independently re-proven in this verification session and can be checked off on that basis.
3. Consider a comment cross-reference in spec.md pointing at design.md's soft-delete decision, so a future reader of the two artifacts side-by-side does not have to independently discover the divergence found here.

### Verdict

**FAIL**

Phases 0-4 (54/54 tasks) are complete, both real test suites reproduce their exact claimed pass counts in this independent re-run (163/163 backend, 211/211 frontend), tsc --noEmit and npm run build are clean, and every architectural/security property named in the verification brief -- the ON-vs-WHERE join placement, use-case-only write routes, retired-slug reservation, untouched stock_movements, no write Route Handler, money-precision-as-string, the real (non-mocked) IDOR test, and product.py's untouched status -- was independently confirmed by reading the real merged code, not trusted from apply-progress.md. However, one CRITICAL, previously-unflagged finding blocks a clean archive: product-persistence/spec.md's literal requirement text for soft_delete's product-to-variant cascade ("both variant rows MUST be marked retired via UPDATE") is directly contradicted by the actual, deliberately-different implementation that design.md documents and the whole test suite validates -- the spec artifact itself was never updated to match, unlike every other design deviation in this change, which design.md's Open Questions section explicitly reconciled. This is a spec-integrity gap, not a functional defect (the described end-user behavior -- variants disappearing from every view after a product retires -- is real and well-tested), but per this verification's hard rule ("a contradiction returns FAIL"), it must be reconciled -- by editing the spec text to match the implemented read-time-cascade behavior, or by implementing row-stamping -- before this change is archived as spec-compliant.
