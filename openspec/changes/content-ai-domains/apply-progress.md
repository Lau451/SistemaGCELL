# Apply Progress: Content + AI Domains

## PR 1 — Migration + Frontend Contract (Phase 1, tasks 1.1-1.6)

Status: Complete.

Zero Gemini dependency. Adds the `short_description` column (D3/DD10's short
catalog blurb, additive alongside the existing `description` long body) and
pins it into the frontend's read contract. No write path, no rendering
behavior yet — those land in later PRs (2, 3, 4).

### Files changed

- `backend/tests/integration/db/test_rls_policies.py` — new test
  `test_restricted_role_reads_short_description_null_on_existing_row`,
  parametrized over `anon`/`authenticated`, proving the column is selectable
  from `catalog_products` and reads back `null` on a pre-existing row.
- `supabase/migrations/20260817000000_products_short_description.sql` (new)
  — `alter table products add column short_description text;` +
  `create or replace view catalog_products` appending the column after
  `created_at` (DD7: append-only, preserves the `anon`/`authenticated`
  grants issued in `20260810000458_public_catalog_rls.sql`).
- `frontend/src/lib/catalog/columns.test.ts` — extended the existing
  column-list assertion to require `short_description`.
- `frontend/src/lib/catalog/columns.ts` — `CATALOG_PRODUCT_COLUMNS` now
  includes `short_description`.
- `frontend/src/lib/catalog/types.ts` — `CatalogProductRow` gains
  `short_description: string | null`.

### Verification (independently re-run by orchestrator)

- `uv run pytest backend/tests/integration/db/test_rls_policies.py -v`
  (local Supabase Postgres, `DB_URL` set) — 66 passed, 0 failed, 0 skipped.
- `npm --prefix frontend test` — 47 files, 344 tests passed.
- Migration schema state confirmed directly against the local Postgres
  container (`\d products`, `\d catalog_products`) — column and view both
  match the migration file.

### Notes

- The local Supabase Postgres volume already had this migration's DDL
  applied from before an earlier interrupted apply session (schema matched,
  but `supabase_migrations.schema_migrations` had no tracked entry for
  `20260817000000` — a CLI bookkeeping gap only, not a schema drift; `npx
  supabase migration up` correctly reported "already exists" on the `alter
  table`, confirming the DB state, not a conflict).
- Rollback boundary (per tasks.md's Suggested Work Units table): revert the
  migration file + the `create or replace view` back to
  `20260811000000`'s definition, and revert `columns.ts`/`types.ts`; no
  later unit depends on this column carrying a value yet.

## PR 2 — Backend Write Path (Phase 2, tasks 2.1-2.8)

Status: Complete (2.1-2.8; 2.9's verify sweep left to the orchestrator/
verify phase, out of this apply batch's assigned scope).

Zero Gemini dependency. `Product` gains `description`/`short_description`
scalars, carried through both repository adapters, the `create`/`update`
use cases, and the admin API request/response models. Base = PR 1 (needs
the `short_description` column to exist).

Strict TDD followed throughout: every GREEN task's RED test was written
and confirmed failing first (see per-task Result notes in `tasks.md` for
the exact failure mode observed at each RED step).

### Files changed

- `backend/tests/unit/products/test_product_domain.py` — extended (task
  2.1's RED target; no `test_product.py` exists, see deviation below) with
  `test_product_description_fields_default_to_none` and
  `test_product_description_fields_can_be_set`.
- `backend/src/gcell/products/domain/product.py` — `Product` gains
  `description: str | None = None`, `short_description: str | None = None`
  after `variants`.
- `backend/tests/integration/db/test_product_repository_adapter_parity.py`
  (new) — round-trips both fields through create/read/update on both
  `PostgresProductRepository` and `InMemoryProductRepository`; asserts an
  update to `short_description` alone leaves `description` unchanged.
- `backend/src/gcell/products/infrastructure/postgres_product_repository.py`
  — `p.description, p.short_description` added to `_SELECT_COLUMNS`,
  `_INSERT_PRODUCT`, `_UPDATE_PRODUCT_FIELDS`, `_rows_to_product`.
- `backend/src/gcell/products/infrastructure/in_memory_product_repository.py`
  — `update()` now carries both fields through; `soft_delete_variant()`
  fixed to do the same (see Issues Found below).
- `backend/src/gcell/products/application/create_product.py`,
  `update_product.py` — two new optional kwargs
  (`description`/`short_description`, default `None`) threaded into the
  `Product` they build/persist.
- `backend/src/gcell/products/application/repository.py` — `update()`
  port docstring extended to note it now persists both text fields.
- `backend/src/gcell/stock/application/create_stocked_product.py` — same
  two kwargs added to `CreateStockedProductUseCase.execute` (see Deviations
  below — this, not `CreateProductUseCase`, is what `admin.py`'s `POST
  /admin/products` actually calls).
- `backend/tests/integration/api/test_admin.py` — extended (task 2.7's RED
  target; no `test_admin_products.py` exists, see deviation below) with
  `test_post_with_description_fields_persists_and_echoes_both`,
  `test_post_omitting_description_fields_leaves_both_null`,
  `test_patch_updates_description_fields_independently`, and
  `test_post_over_cap_short_description_returns_422`.
- `backend/src/gcell/api/admin.py` — `AdminProductResponse` gains
  `description`/`short_description`; `AdminProductWriteRequest` gains both
  as `Field(default=None, max_length=4000/160)`; both write routes
  (`create_admin_product`, `update_admin_product`) pass the two fields
  through to their use cases.

### TDD Cycle Evidence

| Task | RED (test written, confirmed failing) | GREEN (implementation, confirmed passing) | REFACTOR |
|---|---|---|---|
| 2.1/2.2 | `test_product_domain.py`'s two new tests — `AttributeError`/`TypeError` before `Product` had the fields | Added the two dataclass fields — 19/19 `test_product_domain.py` green | None needed |
| 2.3/2.4-2.5 | `test_product_repository_adapter_parity.py` (new) — Postgres round-trip assertion failed (`None == 'Descripcion larga original'`) before the adapters were wired | Both adapters updated — 2/2 parity tests + 30/30 pre-existing `test_product_repository.py` green | Also fixed `in_memory_product_repository.py`'s `soft_delete_variant()` field-drop bug, uncovered while wiring parity |
| 2.6 | Covered transitively by 2.3's and 2.7's RED tests (no dedicated unit test added for the use-case signature change itself — matches tasks.md, which assigns no standalone RED to 2.6) | `create_product.py`/`update_product.py`/`create_stocked_product.py` updated — 159/159 `tests/unit/products` + `tests/unit/stock` green (no regression from the new optional kwargs) | None needed |
| 2.7/2.8 | 4 new `test_admin.py` tests — `KeyError: 'description'` (POST/omit cases) and `422` from `extra=forbid` (PATCH case, before the field existed on the model) | `admin.py` request/response models + both routes updated — 28/28 (+1 skipped, DB-pool-only) `test_admin.py` green | None needed |

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run --project backend pytest tests/unit/products tests/integration/db/test_product_repository.py tests/integration/db/test_product_repository_adapter_parity.py tests/integration/api/test_admin.py -v` (with `DB_URL` set to local Supabase) — 218 passed, 1 skipped (the pre-existing `db_pool`-only IDOR test, itself confirmed green separately, see below), 0 failed |
| Runtime harness command/scenario and exact result | Local Supabase Postgres via `db_conn`/`db_pool` fixtures (`DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres`); `fastapi.testclient.TestClient` for the admin API routes — both exercised directly in the focused run above, not simulated |
| Rollback boundary | Revert `product.py`, both repository adapters, `create_product.py`/`update_product.py`/`create_stocked_product.py`, `repository.py`'s docstring, and `admin.py`'s write/response-model diff; the `short_description` column stays exactly as PR 1 left it (nullable, unread by anything else) |

### Full regression

`DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run
pytest -q` (whole backend suite) — 432 passed, 0 failed, 2 warnings
(pre-existing `httpx`/Pillow deprecation warnings, unrelated to this PR).
`uv run ruff check` on every changed file — all checks passed.

### Deviations

- **2.1's named test file (`test_product.py`) does not exist.** The repo's
  actual domain-test file for `Product`/`ProductVariant` is
  `test_product_domain.py` (present since before this change, covers the
  same class). Extended it rather than creating a second, competing test
  file for the same domain object.
- **2.3's "existing file covering Postgres + in-memory" does not exist for
  `product_repository`** — only `test_product_image_repository_adapter_parity.py`
  does, for the sibling image repository. Created
  `test_product_repository_adapter_parity.py` as a new file, following that
  exact established pattern (design.md's own Testing Strategy row names
  this precedent: "Existing parity suite — extend, do not fork" — there was
  nothing at the `product_repository` level to extend from).
- **2.6's file list omits `stock/application/create_stocked_product.py`.**
  design.md's own File Changes table lists only
  `products/application/{create,update}_product.py`, `register_product.py`
  — but `admin.py`'s `POST /admin/products` route calls
  `CreateStockedProductUseCase` (in `stock/application/`), never
  `CreateProductUseCase` directly (it composes product creation with
  optional initial-stock seeding). Without also updating
  `CreateStockedProductUseCase.execute`, the admin API's create route could
  never round-trip either field — this was required to satisfy the
  explicit acceptance criterion ("admin.py request/response models updated
  so both fields round-trip through the admin API"), so it was made and is
  documented in that file's own docstring, not silently folded in.
- **2.7's named test file (`test_admin_products.py`) does not exist.** The
  repo's actual product-write-route integration test file is
  `test_admin.py` (all existing POST/PATCH/DELETE product route tests live
  there). Extended it rather than forking a parallel file for the same
  routes.

### Issues Found

- `InMemoryProductRepository.soft_delete_variant()` reconstructed its
  `Product` without carrying `description`/`short_description` through —
  retiring a single variant would have silently wiped both text fields on
  the in-memory adapter only (a Postgres/in-memory parity break, and a
  correctness regression for any caller exercising that path against the
  in-memory adapter, e.g. use-case unit tests). Fixed as part of task 2.5
  since it is the same file/method family being touched for parity; not
  separately requested by tasks.md but required for 2.5's own "mirror 2.4
  for parity" instruction to actually hold.

### Not done in this batch (explicitly out of scope)

- Task 2.9 ("Verify `admin-product-management`/`product-persistence` spec
  scenarios") was not marked — the user's instruction scoped this apply
  batch to tasks 2.1-2.8 only. All three spec scenarios named in 2.9 are,
  in fact, already covered by 2.1's and 2.7's RED tests (all green), but
  the task checkbox itself was left for the next batch/verify phase per
  the explicit scope boundary.
- Phases 3+ (`product-form.tsx`, catalog blurb render, alt-text, `ai`/
  `content` domains, wiring) untouched, as instructed.

## PR 3 — Admin Product Form (Phase 3, tasks 3.1-3.3)

Status: Complete. Zero Gemini dependency. Base = PR 2 (needs the admin
API's `description`/`short_description` fields, already accepting and
echoing both). Wires the admin create/edit form to those two fields —
plain, optional, hand-typeable text, no generation trigger anywhere in
this diff (that lands in PR 11).

Strict TDD followed: every GREEN change's RED test was written and
confirmed failing first.

### Files changed

- `frontend/src/app/(admin)/admin/products/product-form.test.tsx` —
  extended with 3 new tests: labeled `description`/`short_description`
  inputs render; submitting with both blank succeeds (`role=alert`
  absent, action called with `formData.get("description") === ""` and
  `formData.get("short_description") === ""`); editing only
  `short_description` on an edit-mode form (`productId` +
  `initialDescription` set) leaves `description` unchanged in the
  submitted `FormData`.
- `frontend/src/app/(admin)/admin/products/product-form.tsx` — new
  `description` `<textarea>` (labeled "Description", `maxLength={4000}`)
  and `short_description` `<input type="text">` (labeled "Short
  description", `maxLength={160}`) rendered between the `Model` field and
  the `Variants` section; new `initialDescription`/
  `initialShortDescription` props (default `""`), threaded through as
  `defaultValue`.
- `frontend/src/app/(admin)/admin/products/actions.test.ts` — extended
  with 3 new tests on `buildProductPayload`'s relay contract: non-blank
  `description`/`short_description` relayed verbatim on create; both
  omitted from the JSON body when blank; on update, `description`
  resubmitted unchanged while only `short_description` is edited.
- `frontend/src/app/(admin)/admin/products/actions.ts` — `ProductWritePayload`
  gains optional `description`/`short_description`; new
  `optionalTrimmedField(formData, key)` helper (mirrors the existing
  `reason`/`initial_quantity` omit-if-blank convention exactly);
  `buildProductPayload` includes either key only when its trimmed value
  is non-empty, so a blank field is dropped from the body entirely
  (`AdminProductWriteRequest`'s `Field(default=None)` then persists
  `null`) rather than sent as `""`.
- `frontend/src/app/(admin)/admin/products/[id]/page.tsx` (deviation, see
  below) — `AdminProduct` interface gains `description: string | null`,
  `short_description: string | null`; both passed to `ProductForm` as
  `initialDescription={product.description ?? ""}` /
  `initialShortDescription={product.short_description ?? ""}`.

### TDD Cycle Evidence

| Change | RED (confirmed failing) | GREEN (confirmed passing) |
|---|---|---|
| `product-form.tsx` inputs + `initial*` props | `npm test -- product-form`: 3/12 failed — `getByLabelText(/short description/i)` threw `TestingLibraryElementError` (no matching element) | 12/12 `product-form.test.tsx` green after adding the two labeled fields and props |
| `actions.ts` `buildProductPayload` relay/omit contract | `npm test -- actions.test`: 2/47 failed — `expected undefined to be 'Descripcion larga'` (create) and `'Descripcion original'` (update), before either field existed on the payload | 47/47 `actions.test.ts` green after `optionalTrimmedField` + the two conditional spreads |

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `npm --prefix frontend test -- product-form` → 12/12 passed; `npm --prefix frontend test -- actions.test` → 47/47 passed |
| Full frontend regression | `npm --prefix frontend test` → 47 files, 350 tests passed (was 344 before this PR; +6 new tests: 3 `product-form.test.tsx`, 3 `actions.test.ts`) |
| Lint | `npx eslint` on all 5 changed files (`product-form.tsx`, `product-form.test.tsx`, `actions.ts`, `actions.test.ts`, `[id]/page.tsx`) — zero warnings/errors |
| Type-check | `npx tsc --noEmit` — zero NEW errors; one pre-existing, unrelated error in `src/lib/catalog/derive.test.ts` (Phase 4 scope, `CatalogProductRow.short_description` missing on a Phase-4 test fixture — not touched, out of this task's scope) |
| Manual `GEMINI_API_KEY`-unset verification (task 3.3, substituted per explicit headless-batch instruction) | `git diff` over `frontend/src/app/(admin)/admin/products/` grepped case-insensitively for `gemini\|generate` — only hit is this diff's own doc-comment stating "no Gemini reference" in prose (mixed-case "Gemini", not the literal uppercase `"GEMINI"` substring `test_frontend_service_role_boundary.py`'s existing `"SERVICE_ROLE" in text` pattern would match once its Phase-6 parametrization lands). No `GEMINI_API_KEY` token, no "Generate" button/label, no `.../generate` fetch call anywhere in `product-form.tsx` or `actions.ts` |
| Rollback boundary | Revert `product-form.tsx`/`actions.ts`, their two test files, and `[id]/page.tsx`'s diff; PR 2's admin API still works via direct (non-form) calls exactly as PR 2 left it |

### Deviations

- **`[id]/page.tsx` is not in design.md's File Changes table for this
  phase** (only `product-form.tsx`/`actions.ts` are named there under
  the combined `{product-form,actions,image-manager}.tsx/.ts` row, which
  is itself the Phase 3+5+11 combined row, not phase-specific). Without
  wiring the edit page's `AdminProduct` fetch/props through to
  `ProductForm`'s new `initialDescription`/`initialShortDescription`,
  the edit form could never display a product's already-persisted copy,
  and — because the form always resubmits both fields' current DOM
  values (by design, so editing one field alone doesn't silently drop
  the other) — an edit form rendered with no `initialDescription` would
  submit `description=""` on every save, silently wiping any
  previously-typed long description the moment an admin changed
  anything else. This directly contradicts spec scenario "Editing
  updates both fields independently." Fixed as part of 3.2, documented
  here rather than silently folded in, matching PR 2's own precedent for
  a File-Changes-table gap (`create_stocked_product.py`).

### Not done in this batch (explicitly out of scope)

- Phase 4+ (public catalog blurb render, alt-text, `ai`/`content`
  domains, wiring, the "Generate copy" trigger) untouched, as instructed.
  `product-form.tsx`'s two new fields are pure hand-typed inputs; no
  Gemini call site, button, or reference exists anywhere in this PR's
  diff — that lands in PR 11 (tasks 11.3-11.4), strictly after `ai`
  (PR 6-7) and `content` (PR 8-10) exist.

## PR 4 — Public Catalog Blurb Render (Phase 4, tasks 4.1-4.6)

Status: Complete. Zero Gemini dependency. Base = PR 2 (needs the
`short_description` column and the admin write path so a real product can
carry a blurb; independent of PR 3). Wires the already-migrated
`short_description` column through the read side of the catalog: derived
card shape → `/api/catalog` response shape → both listing-render paths
(server-rendered first paint and the client-side `/api/catalog` filter/
search/pagination path) → `ProductCard`'s presentational render with
`line-clamp-2` (DD4: never assumes the 160-char cap server-side).

Strict TDD followed: every GREEN change's RED test was written and
confirmed failing first (for 4.1, by stashing the paired `derive.ts` edit
and re-running before restoring it — see per-task Result notes in
`tasks.md`).

### Files changed

- `frontend/src/lib/catalog/derive.test.ts` — fixed the pre-existing
  `short_description`-missing `CatalogProductRow` mock (present since
  PR 1 added the field to the type, never updated on this fixture);
  extended the `deriveListingCard` "composes..." test's `toEqual` with
  `shortDescription: null`; added two new tests deriving a non-null and a
  null `shortDescription` from the row.
- `frontend/src/lib/catalog/derive.ts` — `CatalogListingCard` gains
  `shortDescription: string | null`; `deriveListingCard` populates it
  from `product.short_description`.
- `frontend/src/app/api/catalog/route.ts` — `CatalogListItem` gains
  `shortDescription: string | null`, populated from
  `card.shortDescription` in the `items` map.
- `frontend/src/components/catalog/product-card.test.tsx` — 2 new tests:
  blurb text renders when `shortDescription` is a non-empty string;
  `product-card-blurb` test id is absent (no empty/broken placeholder)
  when `shortDescription` is `null`.
- `frontend/src/components/catalog/product-card.tsx` —
  `ProductCardProps.shortDescription?: string | null` (optional: kept
  every pre-existing call site, including `catalog-listing-view.test.tsx`
  and `catalog-filters.test.tsx`'s untyped fixtures, compiling unchanged);
  renders `<p data-testid="product-card-blurb"
  className="text-muted-foreground line-clamp-2 text-xs">` only when
  truthy.
- `frontend/src/app/(public)/catalog-listing-content.tsx` — the
  server-rendered first-paint card mapping now passes
  `shortDescription: card.shortDescription` through to
  `ProductCardProps`.
- `frontend/src/components/catalog/catalog-filters.tsx` (deviation, see
  below) — `CatalogApiItem` gains `shortDescription: string | null`;
  `toProductCardProps` passes it through.

### TDD Cycle Evidence

| Task | RED (confirmed failing) | GREEN (confirmed passing) |
|---|---|---|
| 4.1/4.2 | Stashed the `derive.ts` GREEN edit, re-ran `derive.test.ts`: 3/10 failed (`toEqual` mismatch on the composed-card test; `undefined` vs the expected string/`null` on the two new tests) | Restored the `derive.ts` edit — 10/10 `derive.test.ts` green |
| 4.3 | Not independently RED-verified as a standalone step — `route.ts`'s `CatalogListItem` change is a pure type/plumbing addition with no dedicated assertion in `route.test.ts` on the `shortDescription` key's presence; covered transitively by `derive.test.ts`'s RED/GREEN cycle for the value it forwards | `route.test.ts`: 12/12 green |
| 4.4/4.5 | `product-card.test.tsx`'s new "renders the shortDescription blurb when present" test: `TestingLibraryElementError` — `getByText("Funda resistente y elegante.")` found nothing, since `ProductCard` didn't accept/render the prop yet | `product-card.tsx` updated — 7/7 `product-card.test.tsx` green |

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `npx vitest run src/lib/catalog/derive.test.ts` → 10/10; `npx vitest run src/app/api/catalog/route.test.ts` → 12/12; `npx vitest run src/components/catalog/product-card.test.tsx` → 7/7; `npx vitest run src/lib/catalog/columns.test.ts src/lib/catalog/queries.test.ts` (task 4.6) → 21/21 |
| Full frontend regression | `npx vitest run` (from `frontend/`) → 47 files, 354 tests passed (was 350 after PR 3; +4 new: 2 `derive.test.ts`, 2 `product-card.test.tsx`) |
| Lint | `npx eslint` on all 7 changed files — zero warnings/errors |
| Type-check | `npx tsc --noEmit` — **zero errors**, including the pre-existing `derive.test.ts` error PR 3's apply-progress flagged as Phase-4 scope; fixed by task 4.1 |
| Task 4.6 column/type/view agreement | `CATALOG_PRODUCT_COLUMNS` = `"id,slug,name,description,created_at,short_description"`; `CatalogProductRow` has the same six keys in the same order; the Phase-1 migration's `catalog_products` view selects the same six columns in the same order — all three still agree column-for-column. The `select("*")`-ban source-grep guard in `queries.test.ts` re-ran green (untouched by this PR — no changes to `queries.ts`) |
| Manual `npm run dev` verification (design.md's "Runtime harness" column) | Substituted with the code-reading + full-suite check above, per the same headless-apply-batch convention PR 3 used for its own manual-verification task (3.3) |
| Rollback boundary | Revert `derive.ts`/`derive.test.ts`, `route.ts`, `product-card.tsx`/`product-card.test.tsx`, `catalog-listing-content.tsx`, and `catalog-filters.tsx`'s diffs; the listing renders with no copy again exactly as PR 1-3 left it |

### Deviations

- **`components/catalog/catalog-filters.tsx` is not in design.md's File
  Changes table for this phase** (only `catalog-listing-content.tsx` and
  `product-card.tsx` are named). `catalog-filters.tsx` is the client
  component that re-fetches `/api/catalog` and rebuilds every
  `ProductCardProps` on every search/model/color/page change — it is the
  *only* code path that renders cards after the first paint. Without
  updating its `CatalogApiItem` interface and `toProductCardProps`
  mapper, the blurb would render once on initial server-side render and
  then silently vanish on the very first filter interaction, which is
  effectively a different bug than "cleanly absent" (spec scenario says
  absent only when the row's `short_description` is actually null) —
  fixed as part of 4.5 and documented here rather than silently folded
  in, matching PR 2/PR 3's own precedent for File-Changes-table gaps
  (`create_stocked_product.py`, `[id]/page.tsx`).
- **`ProductCardProps.shortDescription` made optional
  (`shortDescription?: string | null`), not required.** Two existing test
  fixtures — `catalog-listing-view.test.tsx`'s `CARD_A`/`CARD_B` and
  `catalog-filters.test.tsx`'s `INITIAL_ITEMS` — construct
  `ProductCardProps`-shaped object literals without a `shortDescription`
  key. Making the field required would have forced touching two more
  files outside this phase's explicit scope purely to satisfy the type
  checker, for a field neither test exercises. Every real producer
  (`catalog-listing-content.tsx`, `catalog-filters.tsx`'s
  `toProductCardProps`) always supplies it; `undefined` and `null` are
  handled identically by the render guard (`shortDescription ? ... :
  null`), so this has no runtime behavior difference from a required
  field for any real caller.

### Not done in this batch (explicitly out of scope)

- Phase 5+ (alt-text update path, `ai`/`content` domains, wiring)
  untouched, as instructed. This PR only wires the read/render side of a
  blurb that already exists on a row (via PR 2's write path); no
  generation trigger, no Gemini reference, exists anywhere in this
  diff.

## PR 5 — Alt-Text Update Path (Phase 5, tasks 5.1-5.8)

Status: Complete. Zero Gemini dependency. Base = PR 1 only — independent of
PR 2/PR 3/PR 4's diffs (touches no product-copy field, no admin product
form, no catalog listing). Adds design.md DD3's dedicated
`PATCH /admin/products/{product_id}/images/{image_id}` route: a new
`ProductImageRepository.update_alt_text` port method, both adapters'
implementations, `UpdateProductImageAltTextUseCase` (reproducing the
existing ownership/IDOR guard verbatim from `DeleteProductImageUseCase`),
the FastAPI route (`require_db_pool` only — no `require_storage`, DD3: no
Storage object touched), and a frontend editable alt-text field per image
in `image-manager.tsx` wired to a new `updateProductImageAltTextAction`
Server Action.

Strict TDD followed throughout: every RED test was run and confirmed
failing before its paired GREEN change (see per-task Result notes in
`tasks.md`).

### Files changed

- `backend/tests/unit/products/test_update_product_image_alt_text.py`
  (new) — 6 tests for `UpdateProductImageAltTextUseCase`: updates
  `alt_text` with no other field changed; non-blank stored stripped;
  `None` clears the column; blank-after-strip clears the column; unknown
  image id → `ImageNotFoundError`; cross-parent image id →
  `ImageNotFoundError` with `alt_text` unchanged on the foreign image.
- `backend/src/gcell/products/application/image_repository.py` — new
  `update_alt_text(image_id, alt_text) -> None` Protocol method.
- `backend/src/gcell/products/infrastructure/postgres_product_image_repository.py`
  — `_UPDATE_ALT_TEXT` SQL constant + `update_alt_text`, reusing
  `_rows_affected`; 0 rows → `ImageNotFoundError`.
- `backend/src/gcell/products/infrastructure/in_memory_product_image_repository.py`
  — `update_alt_text` via `dataclasses.replace`; unknown id →
  `ImageNotFoundError`.
- `backend/src/gcell/products/application/update_product_image_alt_text.py`
  (new) — `UpdateProductImageAltTextUseCase`: ownership guard verbatim
  from `DeleteProductImageUseCase`, `_normalize` helper (`None`/
  blank-after-strip → `None`, else `.strip()`), calls
  `image_repository.update_alt_text`, returns the updated `ProductImage`.
- `backend/src/gcell/api/admin.py` — `AdminUpdateImageAltTextRequest`
  (`extra="forbid"`, `alt_text: str | None` required key, no default) +
  `update_admin_product_image_alt_text` `PATCH` route; guard order
  `verify_admin_jwt` (router-level, 401) → `require_db_pool` (503); no
  `require_storage`.
- `backend/tests/integration/api/test_admin_images.py` (deviation, see
  below, in place of the task text's `test_admin_products.py`) — added
  `update-alt-text` to the existing `_IMAGE_ROUTES`/`_STORAGE_TOUCHING_ROUTES`-adjacent
  parametrized 401/503 coverage, plus `update_alt_text` to
  `_spy_all_adapters` and an `"alt-text-json"` `_request_kwargs` case; 4
  new dedicated tests (200 success; 404 cross-parent with a spy proving
  zero writes; 404 unknown id; 422 missing `alt_text` key).
- `backend/tests/unit/products/test_in_memory_product_image_repository.py`,
  `backend/tests/integration/db/test_product_image_repository.py`,
  `backend/tests/integration/db/test_product_image_repository_adapter_parity.py`
  (deviation, see below) — `update_alt_text` port-contract tests added to
  each, matching every sibling method's existing per-adapter test
  convention.
- `frontend/src/app/(admin)/admin/products/image-manager.test.tsx` — 3
  new tests: alt-text input renders per image, pre-filled with the
  image's current `alt_text` (`getAllByLabelText(/^alt text$/i)`,
  disambiguated from the upload form's own "Alt text (optional)" label);
  saving calls `updateProductImageAltTextAction` with
  `product-id`/`image-id`/`alt-text` `FormData` and refreshes the router;
  a failed save surfaces `role=alert` without refreshing. Also added
  `updateProductImageAltTextAction` to the `./actions` mock.
- `frontend/src/app/(admin)/admin/products/image-manager.tsx` — per-image
  `<input id="alt-text-{id}">` (uncontrolled, `defaultValue={image.alt_text
  ?? ""}`, tracked via a `Record<string, HTMLInputElement | null>` ref
  map) + "Save alt text" `Button`; `handleSaveAltText` builds the same
  `FormData` shape as `handleDelete`, calls the new action, and tracks a
  per-image error in `altTextErrors` state (rendered as `role=alert`,
  cleared on success before `router.refresh()`).
- `frontend/src/app/(admin)/admin/products/actions.ts` (deviation, see
  below) — new `updateProductImageAltTextAction(formData)`: relays
  `PATCH .../images/{image_id}` with body `{alt_text}`; a blank submitted
  value is relayed as an explicit `null` (DD3: the key is required, so it
  is never omitted — a blank/`null` is the only way to clear the column).
- `frontend/src/app/(admin)/admin/products/actions.test.ts` (deviation,
  see below) — 4 new tests for `updateProductImageAltTextAction`: JSON
  relay + revalidate on 200; blank input relayed as `alt_text: null`; 404
  returns an error state without revalidating; unauthenticated redirects
  to `/admin/login`.

### TDD Cycle Evidence

| Task | RED (confirmed failing) | GREEN (confirmed passing) |
|---|---|---|
| 5.1 | `ModuleNotFoundError: No module named 'gcell.products.application.update_product_image_alt_text'` collecting the new test file | 6/6 `test_update_product_image_alt_text.py` green after 5.2-5.4 |
| 5.3 (adapter tests, deviation) | Written alongside the GREEN adapter implementation (no separate RED task number in `tasks.md`) — run once implemented; not independently red-verified as a standalone step | 2/2 `test_in_memory_product_image_repository.py`, 2/2 `test_product_image_repository.py`, 1/1 adapter-parity test green |
| 5.5 | `test_admin_images.py`'s 6 new/extended cases: `405 Method Not Allowed` on every `PATCH .../images/{id}` request (route didn't exist yet) | `test_admin_images.py` 24/24 green after 5.6 |
| 5.7 | `image-manager.test.tsx`: 3 failures — `getAllByLabelText(/^alt text$/i)` found nothing (no per-image input rendered yet), `getAllByRole("button", {name: /save alt text/i})` found nothing | `image-manager.test.tsx` 11/11 green after 5.8 |

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run --project backend pytest tests/unit/products/test_update_product_image_alt_text.py tests/integration/api/test_admin_images.py -v -k alt_text` → 10/10 (6 unit + 4 API); `npx vitest run image-manager actions.test.ts` (from `frontend/`) → 62/62 |
| Full backend regression | `uv run --project backend pytest -q` → 448/448 passed |
| Full frontend regression | `npx vitest run` (from `frontend/`) → 47 files, 361 tests passed (was 354 after PR 4; +7 new: 4 `actions.test.ts`, 3 `image-manager.test.tsx`) |
| Lint | `npx eslint` on all 4 changed/new frontend files — 0 errors; 1 pre-existing warning (`@next/next/no-img-element` on the thumbnail `<img>`, unrelated to this diff and already documented in the file's own comment as a deliberate choice) |
| Type-check | `npx tsc --noEmit` — zero errors |
| Runtime harness (design.md's column) | Local Supabase Postgres via `db_conn`/`db_pool` for the two integration test files; substituted the `npm run dev` manual click-through with the code-reading + full-suite check above, per the same headless-apply-batch convention PR 3/PR 4 used |
| Rollback boundary | Revert `image_repository.py`, both adapters' `update_alt_text` (+ their new tests), `update_product_image_alt_text.py` (+ its test file), the `PATCH` route + `AdminUpdateImageAltTextRequest` in `admin.py` (+ `test_admin_images.py`'s new/extended cases), and `image-manager.tsx`/`actions.ts`'s diffs (+ their new tests); upload-time alt text (set via the existing `POST .../images` multipart form field) still works unchanged |

### Deviations

- **`test_admin_products.py` does not exist; extended
  `test_admin_images.py` instead.** Same category of filename deviation
  as PR2's `test_admin.py` substitution — the task text names a file that
  was never created in this repo; `test_admin_images.py` is the actual,
  already-established dedicated integration test file for every
  `/admin/products/{id}/images/...` route (list/upload/delete/reorder),
  including the exact parametrized 401-before-503 guard this task's
  scenario needs. Using it kept the new PATCH route's 401/503 coverage
  free via the existing `_IMAGE_ROUTES` parametrization rather than
  duplicating that guard in a new file.
- **Adapter-level `update_alt_text` tests added to three files not named
  in task 5.3's text** (`test_in_memory_product_image_repository.py`,
  `test_product_image_repository.py`, `test_product_image_repository_adapter_parity.py`).
  Task 5.3 is GREEN-only with no paired RED task number, but every
  sibling port method (`add`, `get_by_id`, `list_for_product`, `delete`,
  `next_sort_order`, `reorder`) already has its own per-adapter test in
  both files, and design.md's own Testing Strategy table explicitly lists
  "Postgres and in-memory repositories round-trip ... `update_alt_text`
  identically" as an adapter-parity requirement. Adding these tests keeps
  that convention and design commitment intact rather than leaving
  `update_alt_text` as the one port method with zero direct adapter
  coverage.
- **`actions.ts`/`actions.test.ts` changed, not named in task 5.8's
  text** (only `image-manager.tsx` is named). Same necessary-but-unlisted
  category as every prior PR's own documented deviations
  (`create_stocked_product.py` in PR2, `[id]/page.tsx` in PR3,
  `catalog-filters.tsx` in PR4): `image-manager.tsx` has no write path of
  its own — every mutation goes through a Server Action in `actions.ts`
  (design.md's "Frontend relay" convention, enforced by every existing
  upload/delete/reorder action) — so the new alt-text `PATCH` route was
  unreachable from the UI without adding one there.

### Not done in this batch (explicitly out of scope)

- Phase 6+ (`ai`/`content` domain scaffold, Gemini adapter, generation
  use cases, generate routes, "Generate" UI triggers) untouched, as
  instructed. This PR only makes an already-set `alt_text` editable by
  hand; no Gemini reference, no generation trigger, exists anywhere in
  this diff.
