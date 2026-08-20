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
