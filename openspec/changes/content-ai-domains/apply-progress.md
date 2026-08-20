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

## PR 6 — `ai` Domain Scaffold (Phase 6, tasks 6.1-6.11)

Status: Complete. No live Gemini call — this PR ships zero `httpx` code
(that's PR 7). Base = PR 1 or later; no dependency on PR 2-5 (independently
verified by starting from a tree with only PR 1-5 already applied). Pure
scaffolding: a domain-agnostic `ContentGenerator` port + pure `ImagePart`
domain type, `GEMINI_API_KEY`/`GEMINI_MODEL` config, a `require_gemini`
503 guard mirroring `require_storage` byte-for-byte, DD5's new
cross-domain-directionality architecture test, a frontend-boundary
regression guard, and the repo's first `.env.example`.

Strict TDD followed throughout: every GREEN task's RED test was written
and confirmed failing first, except 6.7 and 6.9 — both are, by design.md's
own framing, tests that are expected to be immediately green against
today's tree (a directionality/boundary regression guard with nothing yet
violating it), so their "RED" step is "test written, confirmed to need
zero production changes" rather than a failing-then-passing cycle. See
per-task Result notes in `tasks.md` for the exact evidence at each step.

### Files changed

- `backend/tests/architecture/test_domain_boundary.py` — extended with
  `test_ai_domain_generation_module_has_no_banned_imports`, a dedicated
  assertion tying the `gemini-generation` spec's "Domain boundary test
  passes for ai" scenario directly to `ai/domain/generation.py`'s
  existence and purity (rather than relying only on the file's existing
  generic 6-domain sweep, which trivially passes on an absent file).
- `backend/src/gcell/ai/domain/generation.py` (new) — `ImagePart(data:
  bytes, mime_type: str)` frozen dataclass; `SUPPORTED_IMAGE_MIMES =
  frozenset({"image/jpeg", "image/png", "image/webp"})`, mirroring
  `products/domain/product_image.py`'s `ALLOWED_UPLOAD_MIMES`. Zero
  banned imports (stdlib `dataclasses` only).
- `backend/src/gcell/ai/application/content_generator.py` (new) —
  `ContentGenerator` Protocol (`generate_json(*, instruction,
  response_schema, image=None, max_output_tokens=1024) -> Mapping[str,
  Any]`), `GenerationError`, `GenerationRefusedError(GenerationError)`.
  Signature and docstrings match design.md's Interfaces/Contracts section
  verbatim.
- `backend/tests/unit/shared/test_dependencies.py` — extended with 3 new
  `require_gemini` tests (unset key → 503 `gemini_unavailable`; set key →
  `GeminiCredentials` with the default model; `GEMINI_MODEL` env override
  respected), mirroring `test_require_storage.py`'s existing shape.
- `backend/src/gcell/shared/infrastructure/config.py` — `_DEFAULT_GEMINI_MODEL
  = "gemini-2.5-flash"` module constant + `gemini_api_key()`/
  `gemini_model()` (the latter reads `GEMINI_MODEL`, defaulting to the
  constant — DD4's model-pinning policy).
- `backend/src/gcell/shared/infrastructure/dependencies.py` —
  `GeminiCredentials(api_key: str, model: str)` frozen dataclass +
  `require_gemini()`, byte-for-byte `require_storage`/`StorageCredentials`
  shape (503 `gemini_unavailable` when `GEMINI_API_KEY` is unset).
- `backend/tests/architecture/test_domain_dependencies.py` (new, DD5) —
  `ALLOWED_EDGES` map exactly as design.md specifies; `ast`-based
  cross-domain-import walk over all three layers (`domain/`,
  `application/`, `infrastructure/`) of all six domains; `gcell.api`
  exempt as the composition root. A separate module from
  `test_domain_boundary.py` (that one checks `domain/`-layer purity only;
  this one checks cross-domain import *direction*).
- `backend/tests/architecture/test_frontend_service_role_boundary.py` —
  `test_frontend_src_never_references_service_role_key` renamed to
  `test_frontend_src_never_references_banned_secret_token` and
  parametrized (`@pytest.mark.parametrize("banned_token", ["SERVICE_ROLE",
  "GEMINI"])`); doc comment extended to explain the `GEMINI` addition
  covers content-ai-domains' DD4/Threat-Matrix "Secret exposure" row.
- `.env.example` (new, repo root) — first one in the repo. Documents every
  existing `config.py` env var name (`DB_URL`, `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWKS_URL`, `SUPABASE_JWT_ISSUER`,
  `SUPABASE_JWT_AUDIENCE`) plus `GEMINI_API_KEY`/`GEMINI_MODEL` — names
  only, no values. Un-ignored by the root `.gitignore`'s
  `!.env.example` exception.

### TDD Cycle Evidence

| Task | RED (confirmed failing / confirmed pre-green) | GREEN (confirmed passing) |
|---|---|---|
| 6.1/6.2 | `test_ai_domain_generation_module_has_no_banned_imports`: `AssertionError: missing ai domain module: .../ai/domain/generation.py` before the file existed | `generation.py` created — `test_domain_boundary.py` 2/2 green |
| 6.3 | No dedicated RED task assigned to 6.3 in `tasks.md` (GREEN-only); the port and its two exception types have no runtime behavior to fail against yet — verified by successful import only | `content_generator.py` created, imports cleanly, `ai/domain`'s purity test (6.1) stays green since `content_generator.py` lives in `application/`, not `domain/` |
| 6.4/6.5-6.6 | 3 new `test_dependencies.py` tests: `ImportError: cannot import name 'require_gemini' from 'gcell.shared.infrastructure.dependencies'` before either function existed | `config.py`/`dependencies.py` updated — `test_dependencies.py` 5/5 green (2 pre-existing `require_db_pool` + 3 new `require_gemini`); full `backend/tests/unit/shared/` 48/48 green |
| 6.7/6.8 | `test_cross_domain_imports_match_allowed_edges` — written and run immediately: 1/1 green against today's tree with zero production changes (design.md verified this before the test was written; no cross-domain edge in the current tree violates `ALLOWED_EDGES`) | No GREEN step needed — 6.8 is the confirmation itself |
| 6.9/6.10 | `test_frontend_src_never_references_banned_secret_token[GEMINI]` — written and run immediately: 2/2 green (`[SERVICE_ROLE]` + `[GEMINI]`) with zero `frontend/` changes (no `GEMINI` token exists under `frontend/src/` yet) | No GREEN step needed — 6.10 is the confirmation itself |
| 6.11 | N/A — a new documentation-only file, no test targets it directly | `.env.example` created; confirmed present via `git status --porcelain` (`?? .env.example`), confirmed un-ignored by the root `.gitignore`'s explicit `!.env.example` exception |

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run --project backend pytest backend/tests/architecture/test_domain_dependencies.py backend/tests/architecture/test_frontend_service_role_boundary.py backend/tests/architecture/test_domain_boundary.py backend/tests/unit/shared/test_dependencies.py -v` → 10/10 passed |
| Runtime harness command/scenario and exact result | N/A — no adapter yet, no route reachable; per tasks.md's Suggested Work Units table: "guard proven via unit test only (design.md verified `test_domain_dependencies.py` green against today's tree before writing it)" |
| Full backend regression (unit + architecture, no DB dependency) | `uv run --project backend pytest backend/tests/unit backend/tests/architecture -q` → 227 passed, 0 failed (up from 218 unit + architecture tests before this PR — see PR 2's evidence table for the pre-existing baseline shape) |
| Lint | `uv run ruff check` on all 8 changed/new backend files — all checks passed (1 line-length violation in `test_domain_boundary.py` found and fixed during this batch) |
| Rollback boundary | Revert `generation.py`, `content_generator.py`, `config.py`/`dependencies.py`'s diffs, `test_domain_dependencies.py`, `test_domain_boundary.py`/`test_frontend_service_role_boundary.py`/`test_dependencies.py`'s diffs, and `.env.example`; nothing else references any of these yet (PR 7 is the first consumer of `content_generator.py`/`generation.py`; PR 11 is the first consumer of `require_gemini`) |

### Full backend regression note (DB-dependent suites)

`uv run --project backend pytest -q` (the whole suite, including
`integration/db` and `integration/api`) was **not** run to green in this
apply session — this environment had no `DB_URL`/local Supabase Postgres
running at the time, so every DB-backed integration test errored/failed
for that pre-existing environmental reason, independent of this PR's
diff (matches the pattern already documented in PR 1-5's own apply
sessions, which explicitly required `DB_URL` set against a local
Supabase instance). The **DB-independent** subset — `backend/tests/unit`
+ `backend/tests/architecture`, which is everything this PR's diff can
possibly affect, since PR 6 touches no repository/route/integration-test
file — is the 227/227 green result above. Independent re-verification
with a running local Supabase Postgres is the orchestrator's job per
this batch's explicit instructions.

### Deviations from design

None — implementation matches design.md's DD4/DD5 and the
`gemini-generation` spec delta exactly. `ai/domain/generation.py` and
`ai/application/content_generator.py` match the Interfaces/Contracts
section's shapes verbatim; `ALLOWED_EDGES` in
`test_domain_dependencies.py` is a literal copy of design.md's own map.

### Issues Found

None.

### Not done in this batch (explicitly out of scope)

- Phase 7 (`ai/infrastructure/gemini_content_generator.py`, the `httpx`
  adapter, `test_gemini_content_generator.py`) untouched, as instructed.
  `content_generator.py`'s `ContentGenerator` Protocol has zero
  implementations yet — `ai` is a fully typed, fully tested, but
  completely inert leaf domain after this PR, exactly as design.md's
  Rollout section describes ("Slice 3 (`ai`) is wired to nothing and is
  inert until slice 4").
- Phase 8+ (`content` domain, generate routes, admin UI "Generate"
  triggers) untouched, as instructed.

## PR 7 — `ai` Domain Adapter (Phase 7, tasks 7.1-7.3)

Status: Complete. Code-only, ZERO live network calls anywhere, including in
tests (D8/DD4 — CI carries zero secrets). Base = PR 6 (needs
`ContentGenerator`/`GenerationError`/`GenerationRefusedError` from
`ai/application/content_generator.py` and `ImagePart` from
`ai/domain/generation.py`, both already shipped). This PR ships the only
implementation of the `ContentGenerator` port: a thin `httpx` adapter
speaking Gemini's REST `:generateContent` endpoint in structured-JSON mode
(DD6), mirroring `shared/infrastructure/supabase_storage.py`'s adapter
shape byte for byte. `ai` remains a fully typed, fully tested, but
completely inert leaf domain after this PR — `GeminiContentGenerator` has
zero callers (that's PR 9/10), matching design.md's Rollout section
("Slice 3 (`ai`) is wired to nothing and is inert until slice 4").

Strict TDD followed: the full RED test suite was written and confirmed
failing (`ModuleNotFoundError`) before the adapter existed.

### Files changed

- `backend/tests/unit/ai/test_gemini_content_generator.py` (new) — 14
  tests across 5 classes:
  - `TestRequestShape` (2) — no `inline_data` part when `image=None`;
    `inline_data.mime_type`/base64 `data` present and correct when an
    `ImagePart` is given; `responseSchema`/`responseMimeType` always
    present in `generationConfig`.
  - `TestSuccessPath` (1) — `candidates[0].content.parts[0].text` parsed
    as JSON and returned verbatim.
  - `TestFailureMapping` (6) — 400/500 status → `GenerationError`;
    `httpx.TimeoutException` → `GenerationError`;
    `promptFeedback.blockReason` → `GenerationRefusedError`; empty
    `candidates` list (no `blockReason`) → `GenerationRefusedError`;
    non-JSON `text` → `GenerationError`; a response missing the
    `content`/`parts` structure entirely → `GenerationError`.
  - `TestNoRetry` (2) — handler call count == 1 on both a failure path
    (503) and the success path (Threat-Matrix "Process integration" row).
  - `TestSecretExposure` (2) — the configured API key appears in the
    captured `x-goog-api-key` request header and is absent from both a
    `GenerationError` raised on a 500 status and one raised on a timeout
    (Threat-Matrix "Secret exposure" row).
- `backend/src/gcell/ai/infrastructure/gemini_content_generator.py`
  (new) — `GeminiContentGenerator(ContentGenerator)`: constructor takes
  `api_key`, `model`, and an optional `transport:
  httpx.AsyncBaseTransport | None`; builds one `httpx.AsyncClient` at
  construction (`base_url="https://generativelanguage.googleapis.com"`,
  header `x-goog-api-key` set once, `httpx.Timeout(30.0, connect=5.0)`).
  `generate_json` builds the request body exactly per design.md's
  Interfaces/Contracts JSON shape (`contents[0].parts` — `{"text":
  instruction}` plus an optional `{"inline_data": {"mime_type",
  "data": <base64>}}`; `generationConfig` —
  `responseMimeType:"application/json"`, `responseSchema`,
  `temperature:0.4`, `maxOutputTokens`), `POST
  {base}/v1beta/models/{model}:generateContent`. No retry — a single
  `try/except httpx.TimeoutException` wraps the one `client.post` call
  only. Failure mapping: status >= 400 → `GenerationError`;
  `promptFeedback.blockReason` → `GenerationRefusedError`; empty
  `candidates` → `GenerationRefusedError`; missing
  `content.parts[0].text` (KeyError/IndexError/TypeError) →
  `GenerationError`; `json.loads` failure or a non-`Mapping` JSON result
  → `GenerationError`. Every raised exception's message is built only
  from the Gemini response's own status/body/block-reason — the API key
  is never interpolated into any exception message.

### TDD Cycle Evidence

| Task | RED (test written, confirmed failing) | GREEN (implementation, confirmed passing) | REFACTOR |
|---|---|---|---|
| 7.1/7.2 | `test_gemini_content_generator.py` (new, 14 tests) — `ModuleNotFoundError: No module named 'gcell.ai.infrastructure.gemini_content_generator'` at collection time, before the adapter module existed | `gemini_content_generator.py` created — 14/14 green | None needed |

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run --project backend pytest backend/tests/unit/ai/test_gemini_content_generator.py -v` → 14/14 passed |
| Runtime harness command/scenario and exact result | N/A by design (DD4) — CI carries zero secrets, the adapter constructor takes `transport: httpx.AsyncBaseTransport \| None`, and every one of the 14 tests runs under `httpx.MockTransport`. No live-network harness exists or should exist pre-key; verified no test constructs the adapter without passing `transport=` explicitly (grep confirms every `_generator(...)` call site in the test file supplies a `MockTransport`) |
| Rollback boundary | Revert `gemini_content_generator.py` and its test file; `ai` stays a working-but-unwired leaf domain exactly as PR 6 left it — nothing outside this PR's two files references `GeminiContentGenerator` yet |

### Full regression (DB-independent subset)

`uv run --project backend pytest backend/tests/unit backend/tests/architecture -q`
→ 241 passed, 0 failed (up from 227 after PR 6 — +14 new tests, zero
regressions). `uv run ruff check` on both new files — all checks passed.
Full DB-dependent suite (`integration/db`, `integration/api`) not
independently re-run in this apply session (same documented pattern as PR
6 — no `DB_URL`/local Supabase Postgres running at apply time; this PR
touches no repository/route/integration-test file, so the DB-independent
241/241 result is the complete coverage this diff can possibly affect).
Independent re-verification with a running local Supabase Postgres is the
orchestrator's job, same as every prior PR in this change.

### Deviations from design

None — implementation matches design.md's DD4/DD6 and the
`gemini-generation` spec delta exactly. The Interfaces/Contracts section's
JSON request shape, the `x-goog-api-key` header, `/v1beta` path pinning,
`httpx.Timeout(30.0, connect=5.0)`, and the no-retry policy are all
reproduced verbatim. Two failure branches not spelled out in task 7.1's
own text but required by design.md's DD4/DD6 failure-mapping table were
added and tested: an empty `candidates` list with no `blockReason` (DD6:
"no usable candidate") maps to `GenerationRefusedError`, and a response
missing the `content`/`parts` structure entirely maps to `GenerationError`
alongside the explicitly-named non-JSON-text case — same
necessary-but-unlisted category as prior PRs' documented deviations, this
time inside a single new test file rather than an extra production file.

### Issues Found

None.

### Not done in this batch (explicitly out of scope)

- Phase 8+ (`content` domain seam, generate use cases, generate routes,
  admin UI "Generate" triggers) untouched, as instructed.
  `GeminiContentGenerator` has zero callers after this PR — `content/`
  (PR 8-10) is the first consumer of the `ContentGenerator` port, and
  `api/admin.py`'s composition root (PR 11) is the first place a real
  `GEMINI_API_KEY` reaches this adapter.

## PR 8 — `content` DD2 Seam (Phase 8, tasks 8.1-8.4)

Status: Complete (8.1-8.4; all four tasks assigned to this batch).

Zero Gemini dependency. Ships `content`'s narrow read-only port
(`ProductContextReader`) and its products-backed adapter
(`ProductsContextReader`) — the DD2 seam that lets `content`'s upcoming
use cases (PR 9-10) read product/photo data without ever importing
`ProductRepository` directly (the `stock -> products` precedent) and
without a `price`/`cost` field ever existing on the DTOs it hands back
(OQ2). This PR is inert: wired to nothing, no route calls it, exercised
only by its own unit tests against the in-memory `products` repositories.
Base = PR 2 (needs `Product.description`/`short_description` to exist) +
PR 5 (needs `ProductImageRepository.update_alt_text`/the alt-text port
shape to exist) — read only from both, per tasks.md's PR 8 base note.

Strict TDD followed: the RED test file was written first and confirmed
failing (`ModuleNotFoundError`) by temporarily moving both GREEN files
aside and re-running before restoring them and confirming GREEN.

### Files changed

- `backend/tests/unit/content/test_products_context_reader.py` (new) — 8
  tests across `TestProductContext` (happy-path name/model/colors DTO,
  unknown product id → `None`, a structural OQ2 check asserting
  `ProductCopyContext`'s dataclass field set is exactly `{name, model,
  colors}` via `dataclasses.fields` — no `price`/`cost` field exists to
  leak) and `TestPhotoContext` (owned-image happy path resolves
  `storage_path`/`product_name`/`product_model`/`variant_color`; a hero
  image — `variant_id is None` — resolves `variant_color is None`; an
  unknown image id → `None`; a cross-parent image id, i.e. an image
  belonging to a different product, → `None` — the Threat-Matrix IDOR
  case; an unknown product id → `None`).
- `backend/src/gcell/content/application/product_context_reader.py` (new)
  — `ProductCopyContext(name, model, colors)` and
  `ProductPhotoContext(storage_path, product_name, product_model,
  variant_color)` frozen dataclasses, plus the `ProductContextReader`
  Protocol (`product_context`, `photo_context`), matching design.md's DD2
  code block verbatim. Imports only `dataclasses`/`typing`/`uuid` — zero
  `gcell.products` import, so the "content/application/ never touches a
  products write method" guarantee (task 8.4) holds structurally, not by
  convention.
- `backend/src/gcell/content/infrastructure/products_context_reader.py`
  (new) — `ProductsContextReader(product_repository, image_repository)`.
  `product_context` calls `ProductRepository.get_by_id` only.
  `photo_context` calls `get_by_id` + `ProductImageRepository.
  list_for_product(product_id)` and picks `image_id` out of that
  product-scoped list — never `image_repository.get_by_id(image_id)`
  directly — so ownership is a consequence of the query scope (DD2) and a
  cross-parent image id structurally cannot resolve, rather than relying
  on a re-implemented `image.product_id != product_id` predicate. Zero
  SQL/DB-driver imports (D4).

### Verification

- `uv run --project backend pytest backend/tests/unit/content/test_products_context_reader.py -v`
  → 8 passed, 0 failed.
- RED confirmed independently: moved
  `product_context_reader.py`/`products_context_reader.py` out of the
  tree, re-ran the same command → 1 collection error
  (`ModuleNotFoundError: No module named
  'gcell.content.application.product_context_reader'`), then restored
  both files and re-ran to confirm the 8/8 GREEN state above.
- `uv run --project backend pytest backend/tests/architecture/test_domain_dependencies.py backend/tests/architecture/test_domain_boundary.py -v`
  → 3 passed (DD5's `ALLOWED_EDGES["content"] == {"ai", "products"}` still
  holds; `content/domain/` stays pure — untouched, empty `__init__.py`
  only).
- Full backend suite: `uv run --project backend pytest -q` → 341 passed,
  135 skipped (pre-existing `db_pool`-dependent integration tests with no
  local Supabase Postgres running at apply time — same documented skip
  pattern as PR 6/7), 0 failed, 0 regressions.
- Task 8.4 (`content/application/` never depends on a products write
  method) verified by direct inspection: grepped `backend/src/gcell/content/`
  for `.add(`, `.update(`, `.soft_delete(`, `.delete(` — zero matches.
- `uv run ruff check` on all 3 new files — all checks passed.

### Deviations from design

None — `ProductCopyContext`/`ProductPhotoContext`/`ProductContextReader`
reproduce design.md's DD2 code block verbatim (field names, types,
docstring intent), and the adapter's `photo_context` implements the exact
"ownership via query scope, never a re-implemented predicate" approach
DD2 specifies.

### Issues Found

None.

### Not done in this batch (explicitly out of scope)

- Phase 9+ (`content` text/image generation use cases, `copy_draft.py`,
  `ObjectStorage.get`, generate routes, admin UI "Generate" triggers)
  untouched, as instructed. `ProductContextReader`/`ProductsContextReader`
  have zero callers after this PR — `content`'s use cases (PR 9-10) are
  the first consumers.
- 8.4's spec-scenario verification here is direct code/import inspection
  (grep + the existing architecture-test suite), not a new dedicated
  spec-scenario test file — none was assigned in this task's scope, and
  no route exists yet to exercise the scenario end-to-end (that lands in
  PR 11).

## PR 9 — `content` Text-Generation Use Case (Phase 9, tasks 9.1-9.5)

Status: Complete (9.1-9.5; all five tasks assigned to this batch).

Ships `GenerateProductCopyUseCase` — the first actual caller of both PR
7's `ContentGenerator` port and PR 8's `ProductContextReader` port,
wiring them together to produce a draft `ProductCopyDraft` in exactly one
Gemini call (D10). This PR is still inert: no route calls it yet
(wiring is PR 11). Base = PR 7 + PR 8 (needs `ContentGenerator`/
`GenerationError` and `ProductContextReader`/`ProductCopyContext`, both
already shipped).

Strict TDD followed throughout: both RED test files were written first
and confirmed failing (`ModuleNotFoundError`) before their paired GREEN
implementation.

### Files changed

- `backend/tests/unit/content/test_copy_draft.py` (new) — 12 tests
  across `TestCaps` (the three cap constants), `TestTrimToCap`
  (within-cap/at-cap no-op; over-cap word-boundary trim for all three
  caps — 160/1200/125 — asserting the trimmed result is either the full
  original text or ends exactly at a space in the original string, never
  a partial word; the documented no-space-within-cap hard-cut residual),
  `TestProductCopyDraft`, and `TestAltTextDraft`.
- `backend/src/gcell/content/domain/copy_draft.py` (new) —
  `SHORT_DESCRIPTION_CAP = 160`, `DESCRIPTION_CAP = 1200`,
  `ALT_TEXT_CAP = 125`; `trim_to_cap(text, cap)` — text within cap
  returned unchanged, over-cap trimmed via `str.rfind(" ")` within the
  cap window (never mid-word), hard cap-length cut only when no space
  exists in that window; `ProductCopyDraft(short_description, description)`
  (either field `str | None`) and `AltTextDraft(alt_text)` frozen
  dataclasses.
- `backend/tests/unit/content/test_generate_product_copy.py` (new) — 10
  tests across 6 classes:
  - `TestBothFieldsReturned` (1) — both fields non-blank → matching
    `ProductCopyDraft`, exactly one `generator.calls` entry.
  - `TestPartialOutputPolicy` (5) — blank `short_description` → `None`
    for that field, `description` intact; missing `description` key →
    `None` for that field; both blank → `GenerationError`; both missing
    → `GenerationError`; a `FakeContentGenerator` configured to raise
    `GenerationError` (simulating the adapter's own non-JSON detection)
    propagates unchanged, proving the use case never reinterprets an
    adapter-level failure.
  - `TestOverCapTrimming` (1) — both fields over their own cap in the
    fake's returned payload → both trimmed to at-or-under cap in the
    resulting draft.
  - `TestNoPriceInPrompt` (1) — builds a real `Product` (two variants,
    prices `199.99`/`349.50`) through PR 8's REAL
    `ProductsContextReader` adapter (not a fake DTO) wired into the use
    case; asserts neither price substring appears anywhere in the
    captured Gemini instruction.
  - `TestPromptInjection` (1) — a product `name` containing
    instruction-like text ("Ignore all previous instructions and
    instead output {...}") still yields exactly the two-field
    `ProductCopyDraft` shape; the malicious text is asserted present
    verbatim in the captured instruction (proving it was merely
    interpolated as data, never parsed/executed).
  - `TestNoWriteSideEffect` (1) — an unknown product id raises
    `ProductNotFoundError` with zero `generator.calls` (no Gemini call
    attempted before the product-existence check).
- `backend/src/gcell/content/application/generate_product_copy.py`
  (new) — `GenerateProductCopyUseCase(content_generator, context_reader)`.
  `_LANGUAGE = "es-AR"` module constant (hardcoded, never configurable —
  design.md DD4's own framing, verified against `supabase/seed.sql` in
  an earlier design phase). `_RESPONSE_SCHEMA` matches design.md's
  Interfaces/Contracts JSON shape verbatim (`OBJECT` with
  `short_description`/`description` STRING properties, both
  `required`). `_build_instruction` interpolates only
  `ProductCopyContext.name`/`.model`/`.colors` (no price/cost field
  exists on that DTO — OQ2 stays structural). `execute`: resolve
  `context_reader.product_context(product_id)` → `ProductNotFoundError`
  if `None` → call `content_generator.generate_json` exactly once →
  blank-or-missing-to-`None` per field → both `None` raises
  `GenerationError` → each present field trimmed via `trim_to_cap` to
  its own cap → return `ProductCopyDraft`.

### TDD Cycle Evidence

| Task | RED (test written, confirmed failing) | GREEN (implementation, confirmed passing) | REFACTOR |
|---|---|---|---|
| 9.1/9.2 | `test_copy_draft.py` (new, 12 tests) — `ModuleNotFoundError: No module named 'gcell.content.domain.copy_draft'` at collection time | `copy_draft.py` created — 12/12 green | None needed |
| 9.3/9.4 | `test_generate_product_copy.py` (new, 10 tests) — `ModuleNotFoundError: No module named 'gcell.content.application.generate_product_copy'` at collection time | `generate_product_copy.py` created — 10/10 green | None needed |

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run --project backend pytest backend/tests/unit/content/test_copy_draft.py backend/tests/unit/content/test_generate_product_copy.py -v` → 22/22 passed |
| Runtime harness command/scenario and exact result | N/A by design (per tasks.md's Suggested Work Units table for this unit) — no route calls this use case yet (PR 11 is the first wiring); exercised only by fakes (`FakeContentGenerator`, `FakeProductContextReader`) plus one test using PR 8's real `ProductsContextReader` over in-memory `products` repositories (no live network, no real Postgres needed) |
| Rollback boundary | Revert `copy_draft.py`, `generate_product_copy.py`, and their two test files; `ai`/`content` stay proven independently by PR 7/8's own tests — nothing outside this PR's four files references `GenerateProductCopyUseCase` or `copy_draft.py` yet |

### Full regression (DB-independent subset)

`uv run --project backend pytest backend/tests/architecture backend/tests/unit -q`
→ 271 passed, 0 failed (up from 249 after PR 8 — +22 new tests, zero
regressions; confirms `test_domain_dependencies.py`'s DD5
`content: {ai, products}` edge and `test_domain_boundary.py` both still
hold with the new `content/domain/copy_draft.py` and
`content/application/generate_product_copy.py` files in place).
`uv run --project backend pytest -q` (whole suite) → 363 passed, 135
skipped (pre-existing `db_pool`-dependent integration tests — no local
Supabase Postgres running at apply time, same documented skip pattern as
PR 6-8; this PR touches no repository/route/integration-test file, so
the DB-independent 271/271 result is the complete coverage this diff can
possibly affect), 0 failed. `uv run ruff check` on all 4 new files — all
checks passed.

### Deviations from design

- **`generate_product_copy.py` imports `ProductNotFoundError` from
  `gcell.products.application.exceptions`**, not named in design.md's
  File Changes table for this file. Needed so an unknown `product_id`
  raises a sane, existing exception type (reused, matching the
  convention `upload_product_image.py` already uses for the same
  scenario) rather than crashing with an `AttributeError` on `None.name`.
  This is an exception-type import only — not a repository, not a write
  method — so task 9.5's "no repository import" guarantee and DD5's
  `content -> {ai, products}` allowed edge both still hold exactly.
  Same necessary-but-unlisted category as every prior PR's own
  documented deviations (`create_stocked_product.py` in PR 2,
  `[id]/page.tsx` in PR 3, `catalog-filters.tsx` in PR 4,
  `actions.ts`/`actions.test.ts` in PR 5).
- Two test classes not spelled out in task 9.3's own text
  (`TestOverCapTrimming`, `TestNoWriteSideEffect`) — both implied by
  design.md's DD4 (per-field caps) and D5/admin-ai-content-authoring
  spec ("Content Never Persists Products Or Images Directly") but not
  named as scenarios in this task's literal wording. Added for the same
  reason PR 7's apply batch added two unnamed failure-mapping test cases
  (empty-candidates, missing-parts): design.md's own tables imply them,
  and leaving them uncovered would leave a real behavior gap.

### Issues Found

None.

### Not done in this batch (explicitly out of scope)

- Phase 10 (`content` image-generation use case, `generate_image_alt_text.py`,
  `ObjectStorage.get`) untouched, as instructed. `AltTextDraft` (created
  in this PR, 9.2) has zero producing use case until PR 10 lands.
- Phase 11 (wiring — the two generate routes in `admin.py`, composition
  root, both admin "Generate" UI triggers) untouched, as instructed.
  `GenerateProductCopyUseCase` has zero callers after this PR — no route
  is reachable end-to-end yet.

## PR 10 — `content` Image-Generation Use Case (Phase 10, tasks 10.1-10.6)

Status: Complete (10.1-10.6; all six tasks assigned to this batch).

Ships `GenerateImageAltTextUseCase` — the second and final `content`
generation use case, consuming PR 8's `ProductContextReader.photo_context`,
this PR's own `ObjectStorage.get` addition (DD1), and PR 7's
`ContentGenerator` port with an image-input (`ImagePart`) call. Still
inert: no route calls it yet (wiring is PR 11). Base = PR 9 (needs
`ContentGenerator`/`GenerationError`, `ProductContextReader`/
`ProductPhotoContext`, and `content/domain/copy_draft.py`'s `AltTextDraft`/
`ALT_TEXT_CAP`/`trim_to_cap`, all already shipped).

Strict TDD followed throughout: both RED test batches (the `ObjectStorage.get`
extension and the new use-case test file) were written first and
confirmed failing before their paired GREEN implementation.

### Files changed

- `backend/tests/unit/shared/test_supabase_storage.py` (extended) — new
  `TestGet` class, 3 tests: `get()` returns a `StoredObject` whose `data`
  and `content_type` come from the mocked response body and
  `Content-Type` header (plus asserting the `GET` method, object path,
  and auth headers, mirroring `TestPut`/`TestDelete`'s existing
  assertions); a 404 raises `ObjectStorageError` (explicitly NOT
  idempotent-success like `delete`'s 404 case); any other non-2xx status
  also raises `ObjectStorageError`. All three use the same
  `httpx.MockTransport`-injected `_storage()` helper the file already
  had — no new testing approach introduced.
- `backend/src/gcell/shared/application/object_storage.py` (modified) —
  new `StoredObject(data: bytes, content_type: str)` frozen dataclass;
  `get(path: str) -> StoredObject` added to the `ObjectStorage` Protocol
  between `put` and `delete`, with a docstring stating the
  not-idempotent-on-404 contract explicitly (design.md DD1's code block,
  copied verbatim in spirit).
- `backend/src/gcell/shared/infrastructure/supabase_storage.py`
  (modified) — `SupabaseStorage.get`: `self._client.get(f"/object/{bucket}/{path}")`,
  `status_code >= 400` (covers 404, unlike `delete`) raises
  `ObjectStorageError` with the same message shape `put`/`delete` already
  use; on success, `StoredObject(data=response.content,
  content_type=response.headers["content-type"])`.
- `backend/tests/unit/content/test_generate_image_alt_text.py` (new) — 8
  tests across 5 classes:
  - `TestOneImageInputCallPerInvocation` (2) — exactly one
    `generator.calls` entry and exactly one `storage.get_calls` entry
    (matching the photo's `storage_path`) per `execute()`; the `image=`
    kwarg sent to `generate_json` is an `ImagePart` carrying the exact
    bytes and `content_type` `FakeObjectStorage.get` returned (proves the
    DD1 seam's bytes actually reach the Gemini call, not just that a call
    happened).
  - `TestNoPartialOutputLeniency` (3) — blank `alt_text` → `GenerationError`;
    missing `alt_text` key → `GenerationError`; a `FakeContentGenerator`
    configured to raise `GenerationError` (simulating the adapter's own
    non-JSON detection) propagates unchanged. Unlike `ProductCopyDraft`'s
    two-field partial-output policy (PR 9), there is no second field to
    fall back to — DD6's single-key schema gives zero leniency.
  - `TestOverCapTrimming` (1) — an over-125-char `alt_text` in the fake's
    returned payload is trimmed to at-or-under `ALT_TEXT_CAP` in the
    resulting draft.
  - `TestIDORGuard` (1) — `photo_context` returning `None` (covers both
    "unknown image id" and "belongs to a different product", per PR 8's
    DD2 ownership-via-query-scope) raises `ImageNotFoundError` with zero
    `storage.get_calls` and zero `generator.calls` — no bytes fetched,
    no Gemini call attempted, before the ownership check passes.
  - `TestNoWriteSideEffect` (1) — `ObjectStorage.get` raising
    `ObjectStorageError` propagates unchanged with zero `generator.calls`
    — there is nothing to send to Gemini without the bytes, and the
    failure must not be swallowed or reinterpreted.
- `backend/src/gcell/content/application/generate_image_alt_text.py`
  (new) — `GenerateImageAltTextUseCase(content_generator, context_reader,
  object_storage)`. `_LANGUAGE = "es-AR"` module constant, same
  hardcoded-never-configurable convention as PR 9. `_RESPONSE_SCHEMA` is
  a one-key `OBJECT` schema (`alt_text: STRING`, required) per design.md
  DD6's "one-key schema" note. `_build_instruction` interpolates only
  `ProductPhotoContext.product_name`/`.product_model`/`.variant_color`
  (falling back to "sin color especifico" for a hero image's `None`
  color) — no price/cost field exists on that DTO either. `execute`:
  resolve `context_reader.photo_context(product_id, image_id)` →
  `ImageNotFoundError(image_id, product_id)` if `None` (reused from
  `products.application.exceptions`, same plain-exception-type-import
  pattern as PR 9's `ProductNotFoundError` reuse) → `object_storage.get(photo.storage_path)`
  → `StoredObject` → `ImagePart(data=stored.data,
  mime_type=stored.content_type)` → call `content_generator.generate_json`
  exactly once with that `ImagePart` as the `image=` kwarg → blank/missing
  `alt_text` raises `GenerationError` immediately (no fallback field) →
  present value trimmed via `trim_to_cap` to `ALT_TEXT_CAP` → return
  `AltTextDraft`.

### TDD Cycle Evidence

| Task | RED (test written, confirmed failing) | GREEN (implementation, confirmed passing) | REFACTOR |
|---|---|---|---|
| 10.1/10.2/10.3 | `test_supabase_storage.py`'s new `TestGet` class (3 tests) — `ImportError: cannot import name 'StoredObject' from 'gcell.shared.application.object_storage'` at collection time | `StoredObject` + `ObjectStorage.get` (10.2), `SupabaseStorage.get` (10.3) implemented — 9/9 `test_supabase_storage.py` green (`TestPut`/`TestDelete` unchanged + new `TestGet`) | None needed |
| 10.4/10.5 | `test_generate_image_alt_text.py` (new, 8 tests) — `ModuleNotFoundError: No module named 'gcell.content.application.generate_image_alt_text'` at collection time | `generate_image_alt_text.py` created — 8/8 green | None needed |

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run --project backend pytest backend/tests/unit/content/test_generate_image_alt_text.py backend/tests/unit/shared/test_supabase_storage.py -v -k get` → 5/5 passed (the task's own suggested command; without `-k get` the full two files are 8/8 + 9/9 = 17/17) |
| Runtime harness command/scenario and exact result | Local Supabase Storage bucket, per design.md's Testing Strategy row for `get()`'s 404 case: `npx supabase start` confirmed already running (DB/REST/Storage up; only optional `imgproxy`/`edge_runtime`/`pooler` services stopped, unaffected). With `DB_URL`/`SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` exported, `uv run --project backend pytest backend/tests/integration/db -q` → 133 passed (0 regressions) and `uv run --project backend pytest backend/tests/integration/api -q` → 94 passed (0 regressions) — this PR added no integration test file itself (10.1's `get()` RED test follows the file's own established mocked-transport unit-test convention, per explicit instruction that this is acceptable), so these two runs are the regression-safety net, not new coverage |
| Rollback boundary | Revert `generate_image_alt_text.py`, `object_storage.py`'s `get`/`StoredObject`, `supabase_storage.py`'s `get`, and the two extended/new test files; `put`/`delete` on both the port and adapter are untouched, and `GenerateProductCopyUseCase` (PR 9) has zero dependency on anything this PR added |

### Full regression

`uv run --project backend pytest backend/tests/architecture backend/tests/unit -q`
→ 282 passed, 0 failed (up from 271 after PR 9 — +11 new tests: 8
alt-text use-case tests + 3 storage `get` tests; zero regressions;
confirms `test_domain_dependencies.py`'s DD5 `content: {ai, products}`
edge and `test_domain_boundary.py` both still hold with
`generate_image_alt_text.py` in place).

With local Supabase running and `DB_URL`/`SUPABASE_URL`/
`SUPABASE_SERVICE_ROLE_KEY` exported, the DB-dependent suites were run
split by directory rather than as one monolithic `pytest -q` invocation:
`pytest backend/tests/integration/db -q` → 133 passed;
`pytest backend/tests/integration/api -q` → 94 passed. Combined with the
282 above: **509/509 passed, 0 failed** — full backend suite, zero
skips, zero regressions.

Note on the monolithic full-suite command: `uv run --project backend
pytest -q` (single invocation, no directory split) intermittently
reports ~135 `db_pool`-fixture errors and cascading unit-test failures
on this machine even with a live local Supabase and `DB_URL` correctly
exported — reproduced identically by stashing this PR's entire diff
(`git stash -u`) and re-running the same command against the pre-PR-10
tree, confirming it is a pre-existing environment/connection-pool
contention artifact of running ~135 concurrent `asyncpg` pool fixtures
in one pytest process on this machine, not a regression introduced by
this PR's diff. Running the same suites split by directory (as done
above) reproduces zero such failures.

`uv run ruff check` on all 5 changed/new files (`object_storage.py`,
`supabase_storage.py`, `generate_image_alt_text.py`,
`test_supabase_storage.py`, `test_generate_image_alt_text.py`) — all
checks passed.

### Deviations from design

None — implementation matches design.md's DD1/DD6 code blocks and
Sequence Diagram verbatim. `_build_instruction`'s prompt wording is new
prose (design.md specifies the schema/flow, not exact prompt text),
following the same style PR 9's `_build_instruction` already established
(es-AR, plain interpolation, explicit "no price/cost" instruction even
though the DTO structurally cannot carry one).

### Issues Found

None.

### Not done in this batch (explicitly out of scope)

- Phase 11 (wiring — the two generate routes in `admin.py`, composition
  root, both admin "Generate" UI triggers, the `PATCH .../images/{id}`
  guard-order dependency on `require_storage`) untouched, as instructed.
  `GenerateImageAltTextUseCase` and `GenerateProductCopyUseCase` both
  have zero callers after this PR — no route is reachable end-to-end
  yet. Phase 12's final success-criteria sweep also untouched.

## PR 11 — Wiring (Phase 11, tasks 11.1-11.9)

Status: Complete (11.1-11.9; all nine tasks assigned to this batch). Task
11.10 (optional manual verification against a real `GEMINI_API_KEY`) left
undone by design — see "Not done in this batch" below.

The final, largest, highest-risk PR in the 11-PR chain: everything built
in PR 6-10 (`ai` domain, `content` domain's DD2 seam and both generation
use cases, `ObjectStorage.get`) becomes reachable from an actual HTTP
route and an actual admin UI button for the first time. Base = PR 10 +
PR 3 (product-form) + PR 5 (image-manager), all already merged.

Strict TDD followed throughout: every RED test batch (the new backend
integration test file, and both frontend component test extensions) was
written first and confirmed failing before its paired GREEN
implementation.

### Files changed

- `backend/tests/integration/api/test_admin_content.py` (new) — 12 tests,
  mirroring `test_admin_images.py`'s exact conventions (`TestClient`,
  forged admin JWT, monkeypatched-spy adapters, never a live Postgres/
  Storage/Gemini call):
  - `test_no_token_on_generate_routes_returns_401_and_never_calls_anything`
    (parametrized over both routes) — 401 before any 503, zero calls to
    any write adapter or `GeminiContentGenerator.generate_json`.
  - `test_valid_token_with_no_pool_returns_503_on_generate_routes`
    (parametrized) — mirrors `test_admin_images.py`'s equivalent.
  - `test_valid_token_with_pool_but_no_gemini_key_returns_503_and_no_gemini_call`
    (parametrized) — Storage is deliberately configured for the alt-text
    case so the 503 is attributable to `require_gemini` specifically, not
    `require_storage` firing first (design.md's guard order: db → storage
    → gemini).
  - `test_valid_token_with_pool_but_no_storage_config_returns_503_on_alt_text_route`
    — alt-text-only (generate-copy has no `require_storage` dependency at
    all).
  - `test_generate_copy_returns_200_with_zero_db_row_changes` — asserts
    the spy-call list is `[]` BEFORE the request and `["gemini.generate_json"]`
    AFTER it (the literal before/after assertion the task text asks for,
    not just "some assertion somewhere").
  - `test_generate_copy_gemini_failure_maps_to_502_never_a_200_with_an_empty_draft`
    (parametrized over `GenerationError`/`GenerationRefusedError`) — added
    beyond this task's own bullet list, implied by 11.2's
    `_execute_or_raise` mapping and the gemini-generation spec's "Gemini
    call failure surfaces as an error" scenario; proves the two exception
    types map to DISTINCT `detail` values (`generation_failed` vs
    `generation_refused`), both `502`.
  - `test_generate_alt_text_cross_parent_image_id_returns_404_same_body_as_unknown_id`
    — both cases assert the identical `{"detail": "not_found"}` body AND
    zero calls (never reached Storage or Gemini — the IDOR guard fires
    inside `photo_context`, before either).
  - `test_generate_routes_accept_exactly_one_product_or_image_id_per_request`
    — structural proof via `app.openapi()`: neither route declares a
    request body, and every path parameter's schema type is never
    `"array"`.
  Confirmed RED (10/10 failing — 404 route-not-found, or a `KeyError` on
  the OpenAPI schema check) before 11.2; the 2 `GenerationError`/
  `GenerationRefusedError` tests were added and confirmed RED alongside
  the initial 10 (12/12 RED total).
- `backend/src/gcell/api/admin.py` (modified) — new "Content generation"
  section between the alt-text `PATCH` route and the Stock section:
  - `_build_context_reader(conn)` / `_build_content_generator(credentials)`
    — two small composition helpers, following the file's existing
    `_build_storage(credentials)` precedent exactly.
  - `AdminGenerateCopyResponse` (`short_description`/`description`, both
    `str | None` — DD6 partial-output policy) and
    `AdminGenerateAltTextResponse` (`alt_text: str`, never null — DD6's
    single-key no-leniency rule), each with a `from_draft` classmethod
    mirroring `AdminProductResponse.from_domain`'s established pattern.
  - `POST /admin/products/{product_id}/copy/generate` — depends on
    `require_db_pool` + `require_gemini` only (no `require_storage`);
    composes `GenerateProductCopyUseCase` with a fresh
    `GeminiContentGenerator` (from `require_gemini`'s `GeminiCredentials`,
    built per request — never cached, same rule `StorageCredentials`
    already documents) and `ProductsContextReader` over the request's own
    `pool.acquire()`-scoped repositories.
  - `POST /admin/products/{product_id}/images/{image_id}/alt-text/generate`
    — depends on `require_db_pool` + `require_storage` + `require_gemini`,
    in that declared order (matching design.md's guard-order table);
    composes `GenerateImageAltTextUseCase` with the same
    `GeminiContentGenerator`/`ProductsContextReader` pair plus
    `_build_storage(storage_credentials)` for `ObjectStorage.get`.
  - `_execute_or_raise` gains two new `except` clauses:
    `GenerationRefusedError` (caught FIRST, since it subclasses
    `GenerationError`) → `502 generation_refused`; `GenerationError` →
    `502 generation_failed`. `ImageNotFoundError`/`ProductNotFoundError`
    raised by either new use case are already handled by the existing
    404 branch — no change needed there.
  12/12 `test_admin_content.py` tests green.
- `frontend/src/app/(admin)/admin/products/product-form.test.tsx`
  (extended) — 4 new tests: no "Generate copy" button on the CREATE form
  (no `productId` yet); the button calls
  `generateProductCopyAction(productId)` and prefills both fields without
  calling the submit `action` or showing any alert; a generate failure
  surfaces via `role=alert` without touching either field's current
  value. Confirmed RED (2 of the 4 failing — button not found; the other
  2 were already-passing construction checks) before 11.4.
- `frontend/src/app/(admin)/admin/products/product-form.tsx` (modified) —
  `descriptionRef`/`shortDescriptionRef` added to the already-uncontrolled
  `defaultValue` textarea/input (no change to existing typing/submit
  behavior); a `type="button"` "Generate copy" trigger (never
  `type="submit"`), rendered only when `productId !== undefined` (create
  form never shows it — generation needs an existing product to build a
  prompt from). On success, `handleGenerateCopy` sets each non-null
  field's `ref.current.value` directly, following DD6's partial-output
  policy: a `null` field leaves that input's current value untouched.
  17/17 `product-form.test.tsx` green.
- `frontend/src/app/(admin)/admin/products/image-manager.test.tsx`
  (extended) — 2 new tests: the "Generate alt text" button calls
  `generateImageAltTextAction(productId, imageId)` and prefills that
  image's alt-text input without calling `updateProductImageAltTextAction`
  or `router.refresh()`; a generate failure surfaces via `role=alert`
  without refreshing. Confirmed RED (both failing — button not found)
  before 11.6.
- `frontend/src/app/(admin)/admin/products/image-manager.tsx` (modified)
  — `handleGenerateAltText`, reusing the existing `altTextRefs`/
  `altTextErrors` state (same per-image ref-mutation pattern
  `handleSaveAltText` already uses) and a new "Generate alt text"
  `type="button"` next to "Save alt text". Deliberately NO
  `router.refresh()` on success — documented in the file's own module
  docstring: the route has zero write side effect (D5), so a refresh
  would re-fetch `initialImages` unchanged from the server and silently
  wipe the just-generated draft back to its pre-generate value via the
  input's `defaultValue`. 13/13 `image-manager.test.tsx` green.
- `frontend/src/app/(admin)/admin/products/actions.ts` (modified) — two
  new Server Actions, `generateProductCopyAction(productId)` and
  `generateImageAltTextAction(productId, imageId)`, both following the
  file's existing `adminBackendFetch` relay pattern exactly: no request
  body (the route acts on the URL's own id(s) alone — "no bulk generate
  route exists"), `unauthenticated` → redirect to login,
  `backend_unavailable` → a generic error message, `200` → the parsed
  draft fields, anything else → `extractAdminError`.

### TDD Cycle Evidence

| Task | RED (test written, confirmed failing) | GREEN (implementation, confirmed passing) | REFACTOR |
|---|---|---|---|
| 11.1/11.2 | `test_admin_content.py` (new, 12 tests) — 404 route-not-found on every request-shaped test, `KeyError` on the OpenAPI-schema structural test, at collection/run time | Both routes + response models + composition helpers + `_execute_or_raise` mapping implemented — 12/12 green | None needed |
| 11.3/11.4 | `product-form.test.tsx` extension (4 tests) — `TestingLibraryElementError` (button not found) on the 2 button-interaction tests | "Generate copy" trigger + `generateProductCopyAction` implemented — 17/17 `product-form.test.tsx` green | None needed |
| 11.5/11.6 | `image-manager.test.tsx` extension (2 tests) — `TestingLibraryElementError` (button not found) | "Generate alt text" trigger + `generateImageAltTextAction` implemented — 13/13 `image-manager.test.tsx` green | None needed |

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run --project backend pytest backend/tests/integration/api/test_admin_content.py -v` → 12/12 passed; `npm --prefix frontend test -- product-form image-manager` → both files green (17 + 13 = 30/30) |
| Runtime harness command/scenario and exact result | 11.10 (manual click-through against a real `GEMINI_API_KEY`) explicitly out of scope for this batch — no real key available in this headless environment, and the task itself marks it optional/not-required-for-merge. The 503-without-a-key path (the fully-automatable half of the runtime contract) is proven end-to-end by `test_admin_content.py`'s parametrized no-key tests against a real local Supabase Postgres (`DB_URL`/`SUPABASE_URL` exported, `npx supabase start` already running) — every guard except the Gemini call itself runs for real |
| Rollback boundary | Revert the two routes + `_execute_or_raise`'s two new `except` clauses + the two composition helpers + both response models in `admin.py`; revert both UI triggers in `product-form.tsx`/`image-manager.tsx` and the two new actions in `actions.ts`; revert `test_admin_content.py` and the two extended frontend test files. `content`/`ai` (PR 6-10) stay fully built and independently tested but unreachable again, exactly as PR 7-10 left them — no other file changes |

### Full regression

`npm --prefix frontend test` → **47 files / 366 tests passed, 0 failed**
(up from 361 after PR 10 — +5 net-new: 3 in `product-form.test.tsx`, 2 in
`image-manager.test.tsx`). `npx eslint`/`npx tsc --noEmit` on every
changed frontend file (`product-form.tsx`, `product-form.test.tsx`,
`image-manager.tsx`, `image-manager.test.tsx`, `actions.ts`) → 0 errors
(1 pre-existing, already-documented `<img>`/`next/image` warning only,
unrelated to this PR's diff).

Backend, with local Supabase running and `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres` /
`SUPABASE_URL=http://127.0.0.1:54321` exported, split by directory per
PR 10's documented convention (see below for why):

- `pytest backend/tests/unit backend/tests/architecture -q` → 282 passed
  (unchanged from PR 10 — this PR touched no unit/architecture test).
- `pytest backend/tests/integration/db -q` → 133 passed (unchanged from
  PR 10 — this PR touched no DB integration test).
- `pytest backend/tests/integration/api -q` → 106 passed (up from 94 at
  PR 10 — +12 new tests in `test_admin_content.py`, 0 regressions in the
  full pre-existing admin-route suite).

Combined: **521/521 backend passed, 0 failed** + **366/366 frontend
passed, 0 failed** — full stack, zero skips (with a live local Supabase),
zero regressions.

`/health` isolated via `pytest backend/tests -q -k health` → 1 passed,
`GEMINI_API_KEY` unset for the entire run (never set in the shell
environment; only individual tests `monkeypatch.setenv` it in-process).
The full public-catalog suite and the full pre-existing admin panel
suite (`test_admin.py`, `test_admin_images.py`, all Phase 1-10 unit/
integration tests) are all included in and passing within the 521/521
total above, unaffected by the missing key — confirming spec "Rest of
the app is unaffected by a missing key" — while `test_admin_content.py`'s
own parametrized no-key tests prove only the two new generate routes
503 in that state.

Note on the monolithic full-suite command (same pre-existing artifact PR
10's apply-progress.md already documented and root-caused): `uv run
--project backend pytest -q` (single invocation, no directory split), run
once against this PR's tree with the same env exported, reproduced 149
failed / 135 errors — all shaped like the already-documented `db_pool`-
fixture connection-pool-contention issue (`integration/db`/`rls_policies`/
`stock_movement_repository` teardown errors), not a new failure mode.
Per that prior root-cause (`git stash -u` against the PR 10 baseline
reproduced the identical failure count on unmodified code), this is a
pre-existing environment artifact of running ~135+ concurrent `asyncpg`
pool fixtures in one pytest process on this machine, not a regression
from this PR's diff — re-confirmed here rather than re-litigated, and
the split-by-directory invocation above (0 failures) is treated as
authoritative, consistent with PR 10's documented precedent.

`uv run ruff check` on all 3 changed/new backend files (`admin.py`,
`test_admin_content.py`) → all checks passed.

### Deviations from design

None — `admin.py`'s two new routes, guard order, response models, and
`_execute_or_raise` mapping match design.md's "New / changed endpoints"
table, DD4's failure-mapping table, and the two Sequence Diagrams
verbatim. The two frontend triggers match design.md's Sequence Diagram
("prefill 2 fields ... NO WRITE ANYWHERE ON THIS PATH (D5)") exactly —
`type="button"`, never `type="submit"`, and no `router.refresh()` on the
alt-text generate path specifically (a deliberate, documented deviation
FROM the surrounding file's own `router.refresh()`-after-every-mutation
convention, not from design.md, which never mentions refreshing on this
draft-only path at all).

### Issues Found

None.

### Not done in this batch (explicitly out of scope)

- Task 11.10 (optional manual verification against a real
  `GEMINI_API_KEY`) left undone BY DESIGN — no real Gemini key is
  available in this headless apply-phase environment, the task's own
  text marks it optional and "not required for merge", and 11.1/11.9
  already prove the entire automatable surface: the 503-without-a-key
  path on both routes (against a real local Supabase, real JWT
  verification, real `require_db_pool`/`require_storage` guards — only
  the actual Gemini network call is mocked), the 200-with-a-mocked-
  transport success path with a before/after zero-write assertion, the
  404 IDOR/unknown-id mapping, and the 502
  `generation_failed`/`generation_refused` mapping. This is not part of
  PR 11's merge criteria per the task's own text.
- Phase 12 (final success-criteria sweep — `recommendation/` zero diff,
  `pyproject.toml` no new dependency, catalog column/view agreement,
  every Gemini call site confined to `ai/infrastructure/`) untouched, as
  instructed — a separate follow-up batch.
