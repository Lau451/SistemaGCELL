# Tasks: Content + AI Domains (Gemini-Assisted Product Copy)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~2500-3000 total across 11 work units (see per-unit column below) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | 11 work units (below) — design.md's own 4 slices, sub-split per slice-1 blast radius and per adapter/use-case seam |
| Delivery strategy | ask-on-risk |
| Chain strategy | 11 sequential PRs direct to `main` — confirmed by user 2026-08-17, same pattern as `ci-and-rls-tests`/`admin-stock-movement-date-filter` |

Decision needed before apply: Resolved
Chained PRs recommended: Yes
Chain strategy: 11 sequential PRs direct to `main`, each committed, pushed,
and independently verified before the next begins
400-line budget risk: High

Rationale: design.md's own rollout table already calls slice 1 "still high
400-line risk" and pre-authorizes a 1a/1b sub-split ("the migration + view +
pinned-column/type alignment" vs "the backend write path and admin form").
Verified against the File Changes table that even design's own 1b bundle
(`product.py`, both use cases, both repository adapters, `admin.py` write
models, `product-form.tsx`, `actions.ts`, adapter-parity + API integration
tests) is itself ~500+ lines once admin-form UI is included — over budget on
its own. Same pattern repeats in slice 4 (`content`): DD2's ports, DD1's
`ObjectStorage.get`, two generate use cases, two new routes, and two admin UI
triggers do not fit one PR either. Slice 3 (`ai`) splits cleanly along its own
seam — port/config/guard (inert, ~250 lines) vs the `httpx` adapter + its
mock-transport test suite (~350-400 lines, comparable in shape to
`test_supabase_storage.py`). Net: 4 design slices become 11 independently
green, independently revertible units. Units 1-5 carry **zero** Gemini
dependency (design.md's own framing) and are safe to land, merge, and use in
production before `GEMINI_API_KEY` exists anywhere. Units 6-11 are strictly
sequential: `ai` (6-7) must exist before `content` can depend on it (8-11),
and `content`'s two generation flows (text vs. image, units 9-10) split along
DD1/D10's own text-vs-image-input seam before wiring (11) ties routes + admin
UI triggers together.

### Suggested Work Units

| Unit | Goal | Likely PR | Est. lines | Gemini dep? | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|-----------|-------------|----------------------|------------------|--------------------|
| 1 | Migration (`short_description` column + view append, D3/DD7) + pinned frontend column/type contract only — no rendering behavior | PR 1 | ~90-130 | No | `npm --prefix frontend test -- columns queries` ; `uv run --project backend pytest tests/integration/db/test_rls_policies.py -v -k catalog_products` | Local `supabase start`; replay migration, `SELECT` the view directly, confirm `anon` still reads it | Revert the migration file + `create or replace view` back to `20260811000000`'s definition; revert `columns.ts`/`types.ts`; no other unit depends on the column existing yet (all reads are still null) |
| 2 | Backend write path: `Product.description`/`short_description`, `create`/`update`/`register` use cases, both repository adapters, `admin.py` request/response models | PR 2 (base = PR 1) | ~280-360 | No | `uv run --project backend pytest tests/unit/products tests/integration/db/test_product_repository.py tests/integration/api/test_admin_products.py -v` | Local Supabase Postgres via `db_pool`; `fastapi.testclient` | Revert `product.py`, both use cases, both adapters, `admin.py`'s read/write model diff; column stays null exactly as PR 1 left it |
| 3 | Admin product form: two editable copy fields, hand-typed only | PR 3 (base = PR 2) | ~150-200 | No | `npm --prefix frontend test -- product-form` | `npm run dev`; manual create/edit with `GEMINI_API_KEY` unset (spec scenario) | Revert `product-form.tsx`/`actions.ts` diff; PR 2's API still works via direct calls |
| 4 | Public catalog listing renders the blurb | PR 4 (base = PR 2, independent of PR 3) | ~150-200 | No | `npm --prefix frontend test -- catalog-listing-content product-card queries` | `npm run dev`; view `/` with a product that has/lacks `short_description` | Revert `derive.ts`, `route.ts`, `catalog-listing-content.tsx`, `product-card.tsx`, RLS test extension; listing renders no copy again exactly as today |
| 5 | Alt-text update path (DD3): port method, use case, `PATCH` route, editable field in `image-manager.tsx` | PR 5 (base = PR 1, independent of PR 2-4) | ~220-280 | No | `uv run --project backend pytest tests/unit/products/test_update_product_image_alt_text.py tests/integration/api/test_admin_products.py -v -k alt_text` ; `npm --prefix frontend test -- image-manager` | Local Supabase Postgres; `npm run dev` manual alt-text edit on an existing image | Revert `image_repository.py`, both adapters' `update_alt_text`, `update_product_image_alt_text.py`, the `PATCH` route in `admin.py`, `image-manager.tsx` diff; upload-time alt text still works |
| 6 | `ai` domain scaffold: port, pure domain type, `GEMINI_API_KEY`/`require_gemini`, DD5 architecture test, `.env.example` | PR 6 (base = PR 1 or later; no dependency on 2-5) | ~230-260 | Config only, no live call | `uv run --project backend pytest backend/tests/architecture/test_domain_dependencies.py backend/tests/architecture/test_frontend_service_role_boundary.py backend/tests/unit/shared/test_dependencies.py -v` | N/A — no adapter yet, no route reachable; guard proven via unit test only (design.md verified `test_domain_dependencies.py` green against today's tree before writing it) | Revert `generation.py`, `content_generator.py`, `config.py`/`dependencies.py` diffs, `test_domain_dependencies.py`, `.env.example`; nothing else references these yet |
| 7 | `ai` domain adapter: `httpx` Gemini client, mock-transport tested | PR 7 (base = PR 6) | ~350-400 | Yes (code only — zero live calls, D8/DD4) | `uv run --project backend pytest backend/tests/unit/ai/test_gemini_content_generator.py -v` | **N/A — by design (DD4): CI carries zero secrets, adapter constructor takes `transport: httpx.AsyncBaseTransport \| None`, every test runs under `httpx.MockTransport`.** No live-network harness exists or should exist pre-key. | Revert `gemini_content_generator.py` + its test file; `ai` stays a working-but-unwired leaf domain (matches design's "inert until slice 4") |
| 8 | `content` domain DD2 seam: narrow read-only ports + DTOs + products-backed adapter — wired to nothing | PR 8 (base = PR 2 + PR 5, needs both fields and alt-text port to exist) | ~180-220 | No | `uv run --project backend pytest backend/tests/unit/content/test_products_context_reader.py -v` | N/A — inert, no route calls it yet; in-memory products/image repositories only | Revert `product_context_reader.py`, `products_context_reader.py`, their tests; `content/` stays an empty-but-typed package |
| 9 | `content` text-generation use case: `generate_product_copy.py`, `copy_draft.py` (caps/trim, D10), no-price assertion | PR 9 (base = PR 7 + PR 8) | ~260-320 | Yes (unit-tested via fake `ContentGenerator`) | `uv run --project backend pytest backend/tests/unit/content/test_generate_product_copy.py -v` | N/A — no route yet; fake port + fake reader only | Revert `copy_draft.py`, `generate_product_copy.py`, their tests; `ai`/`content` seam still proven independently by PR 7/8's own tests |
| 10 | `content` image-generation use case: `generate_image_alt_text.py`, `ObjectStorage.get` (DD1) on both port and `SupabaseStorage` | PR 10 (base = PR 9) | ~220-280 | Yes (unit-tested) | `uv run --project backend pytest backend/tests/unit/content/test_generate_image_alt_text.py backend/tests/unit/shared/test_supabase_storage.py -v -k get` | Local Supabase Storage bucket for the `get()` integration test (404 → `ObjectStorageError` case needs a real object absence) | Revert `generate_image_alt_text.py`, `object_storage.py`'s `get`, `supabase_storage.py`'s `get`, their tests; `put`/`delete` untouched |
| 11 | Wiring: two `POST .../generate` routes in `admin.py`, composition root, both admin "Generate" triggers, full-stack IDOR/401/503/no-write integration tests | PR 11 (base = PR 10 + PR 3 + PR 5) | ~320-400 | Yes — first slice reachable end-to-end | `uv run --project backend pytest backend/tests/integration/api/test_admin_content.py -v` ; `npm --prefix frontend test -- product-form image-manager` | Manual click-through against a **real** `GEMINI_API_KEY` (proposal's Dependencies: "sdd-apply cannot verify a live call without it" — optional, not blocking; 503-path is fully covered by tests with the key unset) | Revert the two routes + composition wiring + both UI triggers; `content`/`ai` stay fully built and tested but unreachable, exactly as PR 7-10 left them |

## Phase 1: Schema + Frontend Contract (PR 1) — zero Gemini dependency

- [x] 1.1 RED `backend/tests/integration/db/test_rls_policies.py` — extend the
      catalog-view assertion: `anon` selects `short_description` from
      `catalog_products` and it is present (null) on an existing row.
      Result: added `test_restricted_role_reads_short_description_null_on_existing_row`,
      parametrized over `RESTRICTED_ROLES` (`anon`/`authenticated`).
- [x] 1.2 GREEN `supabase/migrations/<ts>_products_short_description.sql` —
      `alter table products add column short_description text;` +
      `create or replace view catalog_products with (security_invoker = false)
      as select id, slug, name, description, created_at, short_description
      from products where deleted_at is null;` (DD7 append-only, preserves
      grants).
      Result: `supabase/migrations/20260817000000_products_short_description.sql`,
      literal SQL from design.md.
- [x] 1.3 Verify Requirement "Short_description defaults to null on existing
      rows" and "Anon can still read the catalog view after the migration"
      (`product-catalog-schema` spec) both pass against 1.1's extended test.
      Result: both scenarios covered by 1.1's new test; full RLS suite green
      (66 passed) against local Supabase Postgres.
- [x] 1.4 RED `frontend/src/lib/catalog/queries.test.ts` (or equivalent
      columns-conformance test) — `CATALOG_PRODUCT_COLUMNS` must include
      `short_description`; existing `select("*")`-ban grep still passes.
      Result: extended `frontend/src/lib/catalog/columns.test.ts`'s existing
      column-list assertion.
- [x] 1.5 GREEN `frontend/src/lib/catalog/columns.ts` — append
      `short_description` to `CATALOG_PRODUCT_COLUMNS` (DD7 column order:
      after `created_at`).
      Result: done, column order matches the view.
- [x] 1.6 GREEN `frontend/src/lib/catalog/types.ts` — add
      `short_description: string | null` to `CatalogProductRow`, matching
      the view column-for-column.
      Result: done.

## Phase 2: Backend Write Path (PR 2, base = PR 1) — zero Gemini dependency

- [x] 2.1 RED `backend/tests/unit/products/test_product.py` — construct
      `Product` without `description`/`short_description`: both default
      `None`, construction does not fail (spec: "Description fields default
      to None").
      Result: no `test_product.py` exists — extended the existing
      `backend/tests/unit/products/test_product_domain.py` (the repo's
      actual domain-test file, same role) with
      `test_product_description_fields_default_to_none` and
      `test_product_description_fields_can_be_set`; confirmed RED
      (`AttributeError`/`TypeError`) before 2.2.
- [x] 2.2 GREEN `backend/src/gcell/products/domain/product.py` — add
      `description: str | None = None`, `short_description: str | None =
      None` after `variants`.
      Result: done; `test_product_domain.py` 19/19 green.
- [x] 2.3 RED extend adapter-parity suite (existing file covering
      Postgres + in-memory) — round-trip both fields through
      create/read/update; update changes only `short_description`,
      `description` unchanged (spec scenarios).
      Result: no product-level parity file existed (only
      `test_product_image_repository_adapter_parity.py` did) — created
      `backend/tests/integration/db/test_product_repository_adapter_parity.py`
      following that exact pattern (both adapters, same operations, same
      final state); confirmed RED against local Supabase Postgres
      (`fetched.description == None` vs expected value) before 2.4.
- [x] 2.4 GREEN `backend/src/gcell/products/infrastructure/postgres_product_repository.py`
      — add `p.description, p.short_description` to `_SELECT_COLUMNS`,
      `_INSERT_PRODUCT`, `_UPDATE_PRODUCT_FIELDS`, `_rows_to_product`.
      Result: done.
- [x] 2.5 GREEN `backend/src/gcell/products/infrastructure/in_memory_product_repository.py`
      — mirror 2.4 for parity.
      Result: done in `update()`; also fixed `soft_delete_variant()`, which
      reconstructed `Product` without carrying `description`/
      `short_description` through — would have silently wiped both fields
      on variant retirement (found during apply, not in the original task
      scope, but required for adapter parity to actually hold).
- [x] 2.6 GREEN `backend/src/gcell/products/application/{create_product,update_product,register_product}.py`
      — carry both fields through as full-replacement scalars (like
      `name`/`model`); `repository.py` docstring updated to note `update`
      now persists both text fields.
      Result: `create_product.py`/`update_product.py` updated with two new
      optional kwargs (default `None`); `register_product.py` needed no
      change (already accepts a fully-built `Product`); `repository.py`
      docstring extended. Also updated
      `backend/src/gcell/stock/application/create_stocked_product.py`
      (`CreateStockedProductUseCase.execute`) — not in design.md's File
      Changes table, but this is the use case `admin.py`'s `POST
      /admin/products` route actually calls (composes with stock seeding),
      not `CreateProductUseCase` directly; without this change the create
      route could never round-trip either field. Deviation documented in
      that file's docstring.
- [x] 2.7 RED `backend/tests/integration/api/test_admin_products.py` —
      create/update a product with both fields via the admin API; response
      echoes both; omitting both on create leaves both null.
      Result: no `test_admin_products.py` exists — extended the existing
      `backend/tests/integration/api/test_admin.py` (the repo's actual
      product-write-route test file) with
      `test_post_with_description_fields_persists_and_echoes_both`,
      `test_post_omitting_description_fields_leaves_both_null`,
      `test_patch_updates_description_fields_independently`, and
      `test_post_over_cap_short_description_returns_422`; confirmed RED
      (`KeyError`/422-from-`extra=forbid`) before 2.8.
- [x] 2.8 GREEN `backend/src/gcell/api/admin.py` — add both fields to the
      product write/response Pydantic models with `Field(max_length=160)`
      (`short_description`) / `Field(max_length=4000)` (`description`) —
      DD4's over-cap-save 422 policy.
      Result: `AdminProductResponse` and `AdminProductWriteRequest` both
      updated; `create_admin_product`/`update_admin_product` routes pass
      both fields through to their use cases. 2.7's 4 RED tests + all
      pre-existing `test_admin.py` tests green (28 passed, 1 skipped
      needing `db_pool` — separately confirmed green against local
      Supabase). Full backend suite: 432/432 passed.
- [ ] 2.9 Verify `admin-product-management`/`product-persistence` spec
      scenarios: "Product is created with only manually typed copy" (key
      unset), "creatable with both fields blank", "editing updates both
      fields independently".

## Phase 3: Admin Product Form (PR 3, base = PR 2)

- [x] 3.1 RED `frontend/src/app/(admin)/admin/products/product-form.test.tsx`
      — form renders two text inputs (`description`, `short_description`);
      submitting with both blank succeeds; editing only one leaves the other
      untouched in the submitted payload.
      Result: 3 new tests added (labeled-inputs render, blank-submit
      succeeds with `role=alert` absent, edit-one-leaves-other-untouched
      via `productId`/`initialDescription`); confirmed RED (`TestingLibraryElementError`
      on `getByLabelText(/short description/i)`) before 3.2. Also added 3
      RED tests to `actions.test.ts` for `buildProductPayload`'s
      omit-if-blank/relay-verbatim contract (not separately named in this
      task, but required for the payload-level half of "editing... leaves
      the other untouched" to actually hold at the `actions.ts` layer, not
      just the form-level `FormData`); confirmed RED
      (`expected undefined to be '...'`) before 3.2.
- [x] 3.2 GREEN `frontend/src/app/(admin)/admin/products/product-form.tsx`,
      `actions.ts` — two editable, optional, hand-typeable fields; no Gemini
      reference anywhere in this diff.
      Result: `product-form.tsx` gains a `description` `<textarea>` and a
      `short_description` `<input type="text">` (labeled "Description"/
      "Short description", client `maxLength` 4000/160 as a UX nicety
      only — server `Field(max_length=...)` 422 stays authoritative),
      plus `initialDescription`/`initialShortDescription` props.
      `actions.ts`'s `buildProductPayload` gains an
      `optionalTrimmedField` helper mirroring the existing `reason`/
      `initial_quantity` omit-if-blank convention: a blank field is
      dropped from the relayed JSON body so `AdminProductWriteRequest`'s
      `Field(default=None)` persists `null`; a non-blank field is relayed
      verbatim. 12/12 `product-form.test.tsx` + 47/47 `actions.test.ts`
      green; full frontend suite 47 files/350 tests green;
      `npx eslint` clean on every changed file; `npx tsc --noEmit` shows
      zero new errors (one pre-existing, unrelated Phase-4
      `derive.test.ts` error only, out of this task's scope).
      Deviation: also updated `[id]/page.tsx` (not named in design.md's
      File Changes table for this phase) — its `AdminProduct` interface
      gained `description`/`short_description`, passed through to
      `ProductForm` as `initialDescription`/`initialShortDescription`.
      Without this, the edit page could never pre-fill either field from
      the already-persisted values, and an edit touching only
      `short_description` would submit `description=""` and silently
      clear it — directly breaking spec scenario "Editing updates both
      fields independently". Same category of necessary-but-unlisted
      deviation as PR2's `create_stocked_product.py` change.
- [x] 3.3 Verify manually with `GEMINI_API_KEY` unset (spec scenario
      precondition) via `npm run dev`.
      Result: substituted with a code-reading check (headless apply
      batch, per explicit orchestrator instruction) — grepped the full
      diff for `frontend/src/app/(admin)/admin/products/` for
      `gemini|generate` (case-insensitive): the only hit is this diff's
      own doc-comment stating "no Gemini reference" in prose, which does
      NOT match `test_frontend_service_role_boundary.py`'s planned
      case-sensitive `"GEMINI" in text` substring check (verified against
      its existing `"SERVICE_ROLE" in text` sibling assertion). No
      `GEMINI_API_KEY` token, no "Generate" button/label, no fetch to any
      `.../generate` route anywhere in `product-form.tsx`/`actions.ts`.
      That guard's Phase-3/5/11-covering parametrization itself is a
      Phase 6 task (6.9), not yet applied — out of this batch's scope.

## Phase 4: Public Catalog Blurb Render (PR 4, base = PR 2)

- [x] 4.1 RED `frontend/src/lib/catalog/derive.test.ts` (or nearest
      existing derive test) — `CatalogListingCard.shortDescription` derives
      from the row's `short_description`.
      Result: fixed the pre-existing `short_description`-missing mock
      (`product: CatalogProductRow`), extended the "composes..." test's
      `toEqual` with `shortDescription: null`, and added two new tests
      (`derives shortDescription from the row's short_description`,
      `derives a null shortDescription when the row's short_description is
      null`). Confirmed RED by stashing the paired `derive.ts` GREEN edit
      and re-running: 3 failures (`undefined` vs expected value/`null`)
      before restoring it.
- [x] 4.2 GREEN `frontend/src/lib/catalog/derive.ts` — add
      `shortDescription` to the derived card shape.
      Result: `CatalogListingCard.shortDescription: string | null` added;
      `deriveListingCard` populates it from `product.short_description`.
      10/10 `derive.test.ts` green.
- [x] 4.3 GREEN `frontend/src/app/api/catalog/route.ts` — add
      `shortDescription` to `CatalogListItem`.
      Result: field added, populated from `card.shortDescription` in the
      `items` map. 12/12 `route.test.ts` green.
- [x] 4.4 RED `frontend/src/app/(public)/__tests__/catalog-listing-content.test.tsx`
      (or `product-card.test.tsx`) — blurb renders when present (spec
      scenario "Listing renders the blurb when present"); renders cleanly,
      no broken placeholder, when null (spec scenario "Listing renders
      cleanly when the blurb is absent").
      Result: no `catalog-listing-content.test.tsx` exists and none was
      created — `catalog-listing-content.tsx` is an async Server Component,
      and this repo's established convention (`revalidate.test.ts`'s own
      doc comment) is that Server Components are not rendered under jsdom;
      only route-segment exports are asserted that way. Rendering
      assertions instead extended the repo's actual rendering-level test,
      `components/catalog/product-card.test.tsx`, with
      `renders the shortDescription blurb when present` and
      `renders cleanly with no blurb placeholder when shortDescription is
      null`; confirmed RED (`TestingLibraryElementError` — blurb text not
      found, since `ProductCard` didn't accept the prop yet) before 4.5.
- [x] 4.5 GREEN `frontend/src/app/(public)/catalog-listing-content.tsx`,
      `components/catalog/product-card.tsx` — render the blurb with
      `line-clamp-2` (DD4: never assumes the 160-char cap server-side).
      Result: `ProductCardProps.shortDescription?: string | null` added;
      renders a `<p data-testid="product-card-blurb"
      className="text-muted-foreground line-clamp-2 text-xs">` only when
      truthy, nothing (no empty placeholder) when null/absent.
      `catalog-listing-content.tsx`'s card-mapping passes
      `card.shortDescription` through. Deviation (same
      necessary-but-unlisted category as PR2/PR3): also updated
      `components/catalog/catalog-filters.tsx` (`CatalogApiItem` +
      `toProductCardProps`) — not in design.md's File Changes table for
      this phase, but it is the client-side `/api/catalog` consumer that
      re-renders cards on every search/filter/pagination action; without
      it the blurb would only ever appear on the first server-rendered
      paint and silently disappear on any filter change. 7/7
      `product-card.test.tsx` green; full frontend suite 47 files/354
      tests green; `npx eslint` clean on every changed file.
- [x] 4.6 Confirm `CATALOG_PRODUCT_COLUMNS`, `CatalogProductRow`, and the
      view (Phase 1) still agree column-for-column; re-run the
      `select("*")` grep guard.
      Result: confirmed unchanged and still aligned —
      `CATALOG_PRODUCT_COLUMNS` = `"id,slug,name,description,created_at,
      short_description"`, `CatalogProductRow` has the same six keys in
      the same order, and the Phase-1 migration's `catalog_products` view
      selects the same six columns in the same order. `columns.test.ts` +
      `queries.test.ts` (incl. the `select("*")` source-grep guard) both
      re-run: 21/21 green. `npx tsc --noEmit` in `frontend/`: zero errors
      (the pre-existing `derive.test.ts` type error from PR1's
      `short_description` addition is now fixed by 4.1).

## Phase 5: Alt-Text Update Path (PR 5, base = PR 1) — zero Gemini dependency

- [x] 5.1 RED `backend/tests/unit/products/test_update_product_image_alt_text.py`
      — updates `alt_text` on an existing image, no other field changes
      (spec scenario); a cross-parent `image_id` (product A referencing
      product B's image) → `ImageNotFoundError`/404, `alt_text` unchanged on
      either image (spec scenario, and design's Threat-Matrix IDOR row).
      Result: new file, 6 tests (update/no-other-field-change, strip
      non-blank, `None` clears, blank-after-strip clears, unknown id 404,
      cross-parent 404 with `alt_text` unchanged on the foreign image);
      confirmed RED (`ModuleNotFoundError` for `update_product_image_alt_text`)
      before 5.2-5.4.
- [x] 5.2 GREEN `backend/src/gcell/products/application/image_repository.py`
      — add `update_alt_text(image_id, alt_text)` port method.
      Result: done; Protocol stub only, mirrors `delete`'s docstring
      convention (0 rows → `ImageNotFoundError`, ownership is a use-case
      concern).
- [x] 5.3 GREEN `backend/src/gcell/products/infrastructure/{postgres,in_memory}_product_image_repository.py`
      — implement `update_alt_text`; 0 affected rows → `ImageNotFoundError`.
      Result: Postgres — `UPDATE product_images SET alt_text = $1 WHERE id
      = $2`, `_rows_affected` reused; in-memory — `dataclasses.replace`.
      Deviation (same necessary-but-unlisted category as prior PRs):
      extended `test_in_memory_product_image_repository.py`,
      `test_product_image_repository.py` (Postgres), and
      `test_product_image_repository_adapter_parity.py` with
      `update_alt_text` port-contract tests — matching every sibling
      method's existing per-adapter test convention and design.md's own
      "Postgres and in-memory repositories round-trip ... `update_alt_text`
      identically" line; all green (2 + 2 + 1 new tests).
- [x] 5.4 GREEN `backend/src/gcell/products/application/update_product_image_alt_text.py`
      — `get_by_id` → `image is None or image.product_id != product_id` →
      `ImageNotFoundError` (reuses the existing ownership-guard pattern
      verbatim, D4).
      Result: `UpdateProductImageAltTextUseCase` — guard verbatim from
      `DeleteProductImageUseCase`; normalizes `alt_text` (`None` or
      blank-after-strip → `None`, else stripped) before calling
      `update_alt_text`, returns the updated `ProductImage` via
      `dataclasses.replace`. 6/6 unit tests green.
- [x] 5.5 RED `backend/tests/integration/api/test_admin_products.py` — `PATCH
      /admin/products/{id}/images/{image_id}` 200 on success; 404 on
      cross-parent/unknown id; 401 with no `Authorization` header **before**
      any 503 check (spec scenario "Unauthenticated alt-text update is
      rejected", Threat-Matrix Routing row); 422 on a body missing
      `alt_text`.
      Result: no `test_admin_products.py` exists — extended
      `backend/tests/integration/api/test_admin_images.py`, the repo's
      actual dedicated admin-image-routes integration test file (a closer
      match than `test_admin.py`, and this file already carries the exact
      401-before-503 parametrized guard this task needs) — same
      deviation-from-literal-filename category as PR2's `test_admin.py`
      substitution. Added `update-alt-text` to the existing
      `_IMAGE_ROUTES`/`_spy_all_adapters` parametrization (401 and 503
      coverage for free) plus 4 dedicated tests: 200 success, 404
      cross-parent (IDOR, `alt_text` spy proves zero writes), 404 unknown
      id, 422 missing `alt_text` key. Confirmed RED (405 Method Not
      Allowed) before 5.6.
- [x] 5.6 GREEN `backend/src/gcell/api/admin.py` — new `PATCH` route, guards
      in order `verify_admin_jwt` (401) → `require_db_pool` (503), no
      `require_storage` (DD3: no Storage object touched here).
      Result: `AdminUpdateImageAltTextRequest` (`extra="forbid"`,
      `alt_text: str | None` required key, no default) +
      `update_admin_product_image_alt_text` route, composing
      `UpdateProductImageAltTextUseCase` with
      `PostgresProductImageRepository`. 24/24 `test_admin_images.py`
      green; full backend suite 448/448 green.
- [x] 5.7 RED `frontend/src/app/(admin)/admin/products/image-manager.test.tsx`
      — alt text is editable on an already-uploaded image.
      Result: 3 new tests (pre-filled editable field per image — asserted
      via `getAllByLabelText(/^alt text$/i)` so the upload form's own "Alt
      text (optional)" label isn't ambiguously matched; save calls
      `updateProductImageAltTextAction` with `product-id`/`image-id`/
      `alt-text` FormData + `router.refresh()`; a failed save surfaces
      `role=alert` and does NOT refresh). Confirmed RED (3 failures —
      label/button not found, action not mocked-exported) before 5.8.
      Also added `updateProductImageAltTextAction` to `./actions`'s mock.
- [x] 5.8 GREEN `frontend/src/app/(admin)/admin/products/image-manager.tsx`
      — editable alt-text field wired to the new `PATCH` route.
      Result: per-image `<input>` (`defaultValue={image.alt_text ?? ""}`,
      uncontrolled via a per-id ref map) + "Save alt text" `Button`,
      `handleSaveAltText` builds the same `FormData` shape as
      `handleDelete` and calls the new
      `updateProductImageAltTextAction`; a per-image error state renders
      `role=alert` without calling `router.refresh()`. Deviation
      (necessary-but-unlisted, same category as prior PRs): added
      `updateProductImageAltTextAction` to `actions.ts` (not itself named
      in this task, but the route has no client-side write path without
      it) — relays `PATCH .../images/{image_id}` with `{alt_text}`, a
      blank submitted value relayed as explicit `null` (DD3: clears the
      column, never omitted since the key is required). Also extended
      `actions.test.ts` with 4 tests for the new action (JSON relay,
      blank→null, 404 error state, unauthenticated redirect) — same
      per-action-file test convention as `reorderProductImagesAction`.
      11/11 `image-manager.test.tsx` + 62/62 combined green; full frontend
      suite 47 files/361 tests green; `npx eslint` clean (0 errors, only
      the pre-existing, unrelated `<img>`/`next/image` warning already
      documented in this file's own comment); `npx tsc --noEmit` zero
      errors.

## Phase 6: `ai` Domain Scaffold (PR 6) — no live Gemini call

- [x] 6.1 RED `backend/tests/architecture/test_domain_boundary.py`-style new
      assertion (or extend it) — `ai/domain/generation.py` imports nothing
      banned (spec `gemini-generation`: "Domain boundary test passes for
      ai").
      Result: added `test_ai_domain_generation_module_has_no_banned_imports`
      to the existing file (reuses its `_banned_imports_in_file` helper);
      confirmed RED (`AssertionError: missing ai domain module`) before 6.2.
- [x] 6.2 GREEN `backend/src/gcell/ai/domain/generation.py` — pure:
      `ImagePart`, `SUPPORTED_IMAGE_MIMES`. Zero banned imports.
      Result: `ImagePart(data: bytes, mime_type: str)` frozen dataclass +
      `SUPPORTED_IMAGE_MIMES = frozenset({"image/jpeg", "image/png",
      "image/webp"})`, mirroring `product_image.py`'s
      `ALLOWED_UPLOAD_MIMES`. 6.1's test green.
- [x] 6.3 GREEN `backend/src/gcell/ai/application/content_generator.py` —
      `ContentGenerator` Protocol (`generate_json`), `GenerationError`,
      `GenerationRefusedError`.
      Result: done, signature matches design.md's Interfaces/Contracts
      section verbatim (`instruction`, `response_schema`, `image`,
      `max_output_tokens`).
- [x] 6.4 RED `backend/tests/unit/shared/test_dependencies.py` (extend) —
      `require_gemini()` raises the 503-mapped error when
      `GEMINI_API_KEY` is unset; a configured key passes through (spec
      "Generate endpoint returns 503 without a key").
      Result: 3 new tests (unset → 503 `gemini_unavailable`; set → returns
      `GeminiCredentials` with the default model; `GEMINI_MODEL` env
      override respected). Confirmed RED
      (`ImportError: cannot import name 'require_gemini'`) before 6.5-6.6.
- [x] 6.5 GREEN `backend/src/gcell/shared/infrastructure/config.py` —
      `gemini_api_key()`, `gemini_model()` (module constant
      `"gemini-2.5-flash"`, optional `GEMINI_MODEL` env override, DD4).
      Result: `_DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"` module constant
      + both functions, mirroring `supabase_service_role_key()`'s
      docstring style.
- [x] 6.6 GREEN `backend/src/gcell/shared/infrastructure/dependencies.py` —
      `GeminiCredentials` + `require_gemini()` → `503 gemini_unavailable`.
      Result: done, byte-for-byte `require_storage`/`StorageCredentials`
      shape. 6.4's 3 RED tests + all 5 pre-existing `test_dependencies.py`
      tests green (8/8); full `backend/tests/unit/shared/` suite 48/48
      green (no regression).
- [x] 6.7 RED `backend/tests/architecture/test_domain_dependencies.py` (new,
      DD5) — write the full `ALLOWED_EDGES` map (`products: set()`,
      `stock: {products}`, `content: {ai, products}`, `ai: set()`,
      `recommendation: set()`, `shared: set()`); run against today's tree
      first to confirm it is green with zero `content`/`ai` cross-imports
      yet (design.md verified this before writing the test).
      Result: new file, `ast`-based cross-domain-import walk (same
      technique as `test_domain_boundary.py`) over all three layers of
      all six domains; `gcell.api` exempt as the composition root. Ran
      immediately green against today's tree — no RED state exists for
      this test by construction (design.md verified this before writing
      it); the RED/GREEN pair here is "test written" (6.7) / "zero prod
      changes needed to pass" (6.8), same shape as 6.9/6.10.
- [x] 6.8 GREEN — no production code change needed for 6.7 to pass; commit
      the test as the executable form of D9's directionality rule.
      Result: confirmed — `test_cross_domain_imports_match_allowed_edges`
      passes with zero `backend/src/gcell/**` changes beyond 6.2/6.3/6.5/6.6
      (all of which stay within `ALLOWED_EDGES`: `ai` imports nothing,
      `shared`'s `dependencies.py`/`config.py` import nothing cross-domain).
- [x] 6.9 RED extend `backend/tests/architecture/test_frontend_service_role_boundary.py`
      — parametrize the guard over `("SERVICE_ROLE", "GEMINI")` (spec
      "Frontend has zero Gemini references").
      Result: `test_frontend_src_never_references_service_role_key`
      renamed to `test_frontend_src_never_references_banned_secret_token`,
      `@pytest.mark.parametrize("banned_token", ["SERVICE_ROLE", "GEMINI"])`.
      Same shape as 6.7: both parametrized cases pass immediately (no
      `GEMINI` token exists under `frontend/src/` yet) — no RED state by
      construction, per design.md's own framing of this task.
- [x] 6.10 GREEN — confirm 6.9 passes with zero code changes (no Gemini
      token exists under `frontend/` yet); this is a regression guard for
      Phase 3/5/11's frontend diffs.
      Result: confirmed — both `[SERVICE_ROLE]` and `[GEMINI]` parametrized
      cases green, zero `frontend/` diff in this PR.
- [x] 6.11 GREEN `.env.example` (new) — `GEMINI_API_KEY=` name only, no
      value; matches `config.py`'s existing reference.
      Result: created at the repo root (first one in the repo, per
      design.md's File Changes table); documents every existing
      `config.py` env var name (`DB_URL`, `SUPABASE_URL`,
      `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWKS_URL`,
      `SUPABASE_JWT_ISSUER`, `SUPABASE_JWT_AUDIENCE`) plus
      `GEMINI_API_KEY`/`GEMINI_MODEL` — names only, no values. Confirmed
      un-ignored by the root `.gitignore`'s `!.env.example` exception
      (`git status --porcelain` shows it as a new untracked file).

## Phase 7: `ai` Domain Adapter (PR 7, base = PR 6)

- [x] 7.1 RED `backend/tests/unit/ai/test_gemini_content_generator.py` (new,
      mirrors `test_supabase_storage.py`) — request body carries
      `responseSchema` + `inline_data` when an `ImagePart` is given, omitted
      when `image=None`; success path parses `candidates[0].content.parts[0].text`
      as JSON; 4xx/5xx → `GenerationError`; `httpx.TimeoutException` →
      `GenerationError`; `promptFeedback.blockReason` →
      `GenerationRefusedError`; non-JSON/malformed text → `GenerationError`;
      handler call count == 1 (no retry, DD4 / Threat-Matrix "Process
      integration" row); `GEMINI_API_KEY` appears only in the `x-goog-api-key`
      request header, never in a raised exception's message (Threat-Matrix
      "Secret exposure" row).
      Result: new file, 14 tests across 5 classes
      (`TestRequestShape`/`TestSuccessPath`/`TestFailureMapping`/
      `TestNoRetry`/`TestSecretExposure`); confirmed RED
      (`ModuleNotFoundError: No module named
      'gcell.ai.infrastructure.gemini_content_generator'`) before 7.2.
      Also covers `no candidates` (empty list, no `blockReason`) as
      `GenerationRefusedError` — DD6's "no usable candidate" case — and a
      missing-`parts`-key malformed response as `GenerationError`, both
      implied by design.md's failure-mapping table but not spelled out in
      this task's own text.
- [x] 7.2 GREEN `backend/src/gcell/ai/infrastructure/gemini_content_generator.py`
      — thin `httpx` adapter, constructor-injected
      `transport: httpx.AsyncBaseTransport | None`, `httpx.Timeout(30.0,
      connect=5.0)`, `POST {base}/v1beta/models/{model}:generateContent`.
      Result: `GeminiContentGenerator(ContentGenerator)` — byte-for-byte
      `SupabaseStorage` adapter shape (constructor-injected `transport`,
      `httpx.AsyncClient` built once in `__init__`); base URL
      `https://generativelanguage.googleapis.com`, `/v1beta` pinned in the
      path (DD4); `x-goog-api-key` header set once at construction, never
      re-derived or logged; request body matches design.md's Interfaces/
      Contracts JSON shape verbatim (`contents[0].parts`,
      `generationConfig.{responseMimeType,responseSchema,temperature:0.4,
      maxOutputTokens}`); `httpx.TimeoutException` caught around the single
      `client.post` call only (no retry loop — DD4/D6). 14/14 7.1 tests
      green.
- [x] 7.3 Verify `gemini-generation` spec scenarios: "Adapter tests run
      offline" (zero network calls under `httpx.MockTransport`), "Gemini
      call failure surfaces as an error" (never `200` with an empty draft).
      Result: both scenarios hold — every one of 7.1's 14 tests constructs
      the adapter with `transport=httpx.MockTransport(handler)` only (no
      base `httpx.Client`/`AsyncClient` default transport reachable, no
      real socket opened); `TestFailureMapping`'s 6 cases and
      `TestSecretExposure`'s 2 cases all assert a raised exception
      (`GenerationError`/`GenerationRefusedError`), never a `200` return
      value, for every failure mode design.md's DD4 table lists (4xx, 5xx,
      timeout, safety block, no candidates, non-JSON text, malformed
      structure).

## Phase 8: `content` DD2 Seam (PR 8, base = PR 2 + PR 5)

- [x] 8.1 RED `backend/tests/unit/content/test_products_context_reader.py`
      (new) — `photo_context` returns `None` for another product's image id
      and for an unknown id (spec `admin-ai-content-authoring` /
      Threat-Matrix "IDOR" row, DD2's ownership-via-query-scope design).
      Result: new file, 8 tests across `TestProductContext`/
      `TestPhotoContext` (happy-path `product_context`, unknown-product-id
      → `None`, a structural OQ2 no-price/no-cost field-set assertion via
      `dataclasses.fields`, owned-image happy path, hero-image
      `variant_color is None`, unknown image id → `None`, cross-parent
      image id (IDOR) → `None`, unknown product id → `None`). Confirmed RED
      (`ModuleNotFoundError: No module named
      'gcell.content.application.product_context_reader'`) by temporarily
      moving both 8.2/8.3 files aside and re-running before restoring them.
- [x] 8.2 GREEN `backend/src/gcell/content/application/product_context_reader.py`
      — `ProductCopyContext` (name, model, colors — **no price/cost field**,
      OQ2), `ProductPhotoContext`, `ProductContextReader` Protocol.
      Result: done, matches design.md's DD2 code block verbatim
      (`ProductCopyContext`/`ProductPhotoContext` frozen dataclasses +
      `ProductContextReader` Protocol with `product_context`/
      `photo_context`); imports nothing from `products` — pure DTOs/typing
      only, so the "no write method reachable from `application/`"
      guarantee in 8.4 holds by construction, not just by convention.
- [x] 8.3 GREEN `backend/src/gcell/content/infrastructure/products_context_reader.py`
      — adapter over `ProductRepository`/`ProductImageRepository`
      (`list_for_product` → pick `image_id`, D4: no SQL).
      Result: `ProductsContextReader(product_repository, image_repository)`
      — `product_context` calls `get_by_id` only; `photo_context` calls
      `get_by_id` + `list_for_product(product_id)` and picks `image_id`
      out of that product-scoped list (never `image_repository.get_by_id`
      directly), so a cross-parent image id structurally cannot resolve —
      ownership via query scope exactly as DD2 specifies. Zero DB-driver
      imports (D4). 8/8 tests from 8.1 green.
- [x] 8.4 Verify spec `admin-ai-content-authoring` "Content has no products
      repository": `content/application/` depends on `ai` and on
      `products` only through this adapter, never a write method.
      Result: confirmed — `product_context_reader.py` (application layer)
      imports only `dataclasses`/`typing`/`uuid`, zero `gcell.products`
      import; only `products_context_reader.py` (infrastructure layer)
      imports `ProductRepository`/`ProductImageRepository`, and calls only
      `get_by_id`/`list_for_product` (read methods) — grepped
      `content/` for `.add(`/`.update(`/`.soft_delete(`/`.delete(` calls:
      zero matches. `test_domain_dependencies.py` (DD5,
      `content: {ai, products}`) and `test_domain_boundary.py` both still
      green. Full backend suite: 341 passed, 135 skipped (pre-existing
      `db_pool`-dependent tests, same skip pattern as prior PRs), 0
      failures — no regression.

## Phase 9: `content` Text-Generation Use Case (PR 9, base = PR 7 + PR 8)

- [x] 9.1 RED `backend/tests/unit/content/test_copy_draft.py` — over-cap
      output trims at the last word boundary within the cap (blurb 160,
      body 1200 chars, DD4).
      Result: new file, 12 tests across `TestCaps`/`TestTrimToCap`/
      `TestProductCopyDraft`/`TestAltTextDraft` — cap-value assertions,
      within-cap/at-cap no-op, over-cap word-boundary trim for all three
      caps (160/1200/125), the documented no-space-within-cap hard-cut
      residual, and both draft dataclasses' field shapes. Confirmed RED
      (`ModuleNotFoundError: No module named 'gcell.content.domain.copy_draft'`)
      before 9.2.
- [x] 9.2 GREEN `backend/src/gcell/content/domain/copy_draft.py` —
      `ProductCopyDraft`, `AltTextDraft`, the three caps (160/1200/125),
      `trim_to_cap`.
      Result: done, matches design.md's DD4 table verbatim (word-boundary
      trim via `rfind(" ")`, hard-cut fallback documented as the residual
      when no space exists within the cap). 12/12 9.1 tests green.
      `AltTextDraft` created but has zero producing use case until PR 10,
      as the task text anticipates.
- [x] 9.3 RED `backend/tests/unit/content/test_generate_product_copy.py`
      (fake `ContentGenerator` + fake `ProductContextReader`) — both fields
      returned → draft (spec "One click yields both draft fields", exactly
      one Gemini call, D10); one field blank/missing → `200`-shaped draft
      with that field `null` (DD6 partial-output policy); both blank/missing
      or non-JSON → `GenerationError`; **prompt string contains no price**
      even with a product carrying variants of different prices (spec
      "Price is absent from the generation input"); a product `name`
      containing instruction-like text still yields schema-shaped output
      that writes nothing (Threat-Matrix "Prompt injection" row).
      Result: new file, 10 tests across 6 classes. The no-price test uses
      the REAL PR-8 `ProductsContextReader` adapter over an in-memory
      `products` repository holding a `Product` with two variants of
      different prices (`199.99`/`349.50`), asserting neither price
      string appears in the captured instruction — proves price is
      stripped by the actual DD2 seam, not just absent from a fake DTO.
      Also added `TestOverCapTrimming` (per-field cap application) and
      `TestNoWriteSideEffect` (unknown product id raises before any
      Gemini call, zero generator calls) — implied by design.md's DD4/D5
      but not spelled out in this task's own text. Confirmed RED
      (`ModuleNotFoundError: No module named
      'gcell.content.application.generate_product_copy'`) before 9.4.
- [x] 9.4 GREEN `backend/src/gcell/content/application/generate_product_copy.py`
      — builds the `es-AR` prompt (name/model/colors only), calls
      `ContentGenerator.generate_json` exactly once, applies per-field caps.
      Result: `GenerateProductCopyUseCase(content_generator, context_reader)`
      — `_LANGUAGE = "es-AR"` module constant (hardcoded, not
      configurable, per design.md DD4); `_RESPONSE_SCHEMA` matches
      design.md's Interfaces/Contracts JSON shape verbatim; prompt built
      only from `ProductCopyContext.{name,model,colors}`. Partial-output
      policy: both blank/missing → `GenerationError`; exactly one
      blank/missing → draft with that field `None`; each present field
      independently trimmed via `trim_to_cap`. Unknown product id →
      `ProductNotFoundError` (reused from
      `products.application.exceptions` — a plain exception-type import,
      not a repository dependency; content→products stays an allowed
      DD5 edge) raised before any Gemini call. 10/10 9.3 tests green.
- [x] 9.5 Verify spec `admin-ai-content-authoring` "Generating copy does not
      persist anything": the use case's only dependencies are
      `ContentGenerator` and `ProductContextReader` — no repository import.
      Result: confirmed — `GenerateProductCopyUseCase`'s only two
      constructor fields are `content_generator: ContentGenerator` and
      `context_reader: ProductContextReader`; grepped the file for
      `.add(`/`.update(`/`.soft_delete(`/`.delete(`/`Repository`: zero
      matches beyond doc-comment prose. `test_domain_dependencies.py`
      (DD5, `content: {ai, products}`) and `test_domain_boundary.py` both
      still green (271/271 `tests/unit` + `tests/architecture`). Full
      backend suite: 363 passed, 135 skipped (pre-existing
      `db_pool`-dependent tests, no local Supabase running at apply
      time — same documented pattern as PR 6-8), 0 failed.

## Phase 10: `content` Image-Generation Use Case (PR 10, base = PR 9)

- [ ] 10.1 RED `backend/tests/unit/shared/test_supabase_storage.py` (extend)
      — `get()` returns `StoredObject(data, content_type)` from the response
      body/header; a 404 → `ObjectStorageError` (not silently swallowed,
      unlike `delete`).
- [ ] 10.2 GREEN `backend/src/gcell/shared/application/object_storage.py` —
      `StoredObject` dataclass, `get(path) -> StoredObject` on the
      `ObjectStorage` Protocol (DD1).
- [ ] 10.3 GREEN `backend/src/gcell/shared/infrastructure/supabase_storage.py`
      — `GET /object/{bucket}/{path}`, non-2xx → `ObjectStorageError`.
- [ ] 10.4 RED `backend/tests/unit/content/test_generate_image_alt_text.py`
      — one Gemini image-input call per invocation, targets exactly one
      image (spec "Alt text generation targets one image"); returns a draft
      `alt_text`, applies to no other image; blank/missing `alt_text` →
      `GenerationError` (DD6: single-key schema, no partial-output leniency
      for alt text).
- [ ] 10.5 GREEN `backend/src/gcell/content/application/generate_image_alt_text.py`
      — `photo_context` (Phase 8) → `ObjectStorage.get` (10.2) →
      `ContentGenerator.generate_json` with an `ImagePart`.
- [ ] 10.6 Verify spec "Generating alt text does not persist anything": no
      repository/storage write call anywhere in this use case's dependency
      graph.

## Phase 11: Wiring — Routes + Admin UI Triggers (PR 11, base = PR 10 + PR 3 + PR 5)

- [ ] 11.1 RED `backend/tests/integration/api/test_admin_content.py` (new) —
      unauthenticated request to each new generate route → `401` **before**
      any `503` (Threat-Matrix "Routing" row); `GEMINI_API_KEY` unset →
      `503` on both generate routes, **no Gemini call attempted** (spec
      "Generate endpoint returns 503 without a key"); with a key configured
      and a mocked transport, generate-copy returns `200` with **zero** DB
      row changes (assert before/after, spec "zero write side effect");
      cross-parent `image_id` on the alt-text generate route → `404`, same
      body shape as an unknown id (Threat-Matrix IDOR row, mirrors 5.1/5.5);
      no route accepts more than one `product_id`/`image_id` per request
      (spec "No bulk generate route exists").
- [ ] 11.2 GREEN `backend/src/gcell/api/admin.py` — `POST
      /admin/products/{id}/copy/generate` and `POST
      /admin/products/{id}/images/{image_id}/alt-text/generate`; guard order
      401 → `require_db_pool` 503 → (alt-text only) `require_storage` 503 →
      `require_gemini` 503; `GenerationError` → `502 generation_failed`,
      `GenerationRefusedError` → `502 generation_refused` in
      `_execute_or_raise`; wire the DD2 adapter (Phase 8) and the Gemini
      adapter (Phase 7) at the composition root.
- [ ] 11.3 RED `frontend/src/app/(admin)/admin/products/product-form.test.tsx`
      (extend) — "Generate copy" button calls the new endpoint and prefills
      both fields **without** submitting the form (D5: no write on this
      path).
- [ ] 11.4 GREEN `frontend/src/app/(admin)/admin/products/product-form.tsx`,
      `actions.ts` — add the "Generate copy" trigger calling
      `POST .../copy/generate`; prefill only, existing Save button (Phase
      3) remains the only write path.
- [ ] 11.5 RED `frontend/src/app/(admin)/admin/products/image-manager.test.tsx`
      (extend) — "Generate alt text" button calls the new endpoint and
      prefills the alt-text input without submitting.
- [ ] 11.6 GREEN `frontend/src/app/(admin)/admin/products/image-manager.tsx`
      — add the "Generate alt text" trigger; existing PATCH save (Phase 5)
      remains the only write path.
- [ ] 11.7 Verify upload does not auto-trigger generation (spec "Upload
      does not auto-trigger alt-text generation" — construction-only check,
      no new code path connects upload to generate).
- [ ] 11.8 Re-run 6.9/6.10's parametrized `test_frontend_service_role_boundary.py`
      guard — confirm the new frontend diff still contains zero `GEMINI`
      tokens.
- [ ] 11.9 Full regression: `npm --prefix frontend test && uv run --project
      backend pytest -q`; with `GEMINI_API_KEY` unset, confirm `/health`,
      the full public catalog, and the full existing admin panel are
      unaffected and only the two generate endpoints return `503` (spec
      "Rest of the app is unaffected by a missing key").
- [ ] 11.10 Optional manual verification against a real `GEMINI_API_KEY`
      (proposal's Dependencies) — not required for merge; the 503 path is
      already proven by 11.1/11.9.

## Phase 12: Final Success-Criteria Sweep

- [ ] 12.1 Confirm `backend/src/gcell/recommendation/` is unchanged (D1) —
      zero diff.
- [ ] 12.2 Confirm `backend/pyproject.toml` has no new runtime dependency
      (D8) — `httpx` was already present.
- [ ] 12.3 Confirm `CATALOG_PRODUCT_COLUMNS`, `CatalogProductRow`, and the
      `catalog_products` view still agree column-for-column, and no query
      anywhere uses `select("*")`.
- [ ] 12.4 Confirm every Gemini call site is under `ai/infrastructure/`,
      reachable only through an admin-authenticated route, and grep
      `frontend/` for `GEMINI`/`generateContent`/Gemini SDK names returns
      nothing.
