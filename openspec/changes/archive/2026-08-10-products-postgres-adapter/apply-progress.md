# Apply Progress: products-postgres-adapter

## Batch: PR1 — Phase 1 Domain Realignment

**Branch**: `pr1-products-domain-realignment` (branched from `main`)
**Mode**: Strict TDD
**Scope**: Phase 1 tasks only (1.1-1.7). Phase 2 (Postgres adapter) and Phase 3
(stock domain) are separate PRs, NOT touched in this batch. Frontend / public
catalog untouched.

### Completed Tasks (7/7 in Phase 1)

- [x] 1.1 [RED] Rewrote `test_product_domain.py`: id-based eq/hash, Decimal price/cost, slug/model/color invariants
- [x] 1.2 [GREEN] Rewrote `products/domain/product.py`: `@dataclass(eq=False)` `Product{id,slug,name,model,variants}` / `ProductVariant{id,color,price:Decimal,cost:Decimal}`; explicit `__eq__`/`__hash__` on `id`; slug regex+length, Decimal-type/finite/`>=0`/scale-2 checks
- [x] 1.3 [RED] Rewrote `test_register_product_use_case.py` for async `execute` + `get_by_slug`/`get_by_id`
- [x] 1.4 [GREEN] Made `products/application/repository.py` async: `add`/`get_by_id`/`get_by_slug`/`list_all`, dropped `get_by_name`
- [x] 1.5 [GREEN] Created `products/application/exceptions.py`: `DuplicateProductSlugError`
- [x] 1.6 [GREEN] Updated `register_product.py`: async `execute`, removed the `get_by_slug` pre-check (duplicate detection now solely via `repository.add` raising `DuplicateProductSlugError`)
- [x] 1.7 [GREEN] Updated `in_memory_product_repository.py`: async, id-keyed dict + slug index, raises `DuplicateProductSlugError` on slug collision

### Files Changed

| File | Action | What Was Done |
|------|--------|----------------|
| `backend/src/gcell/products/domain/product.py` | Modified | `Product{id,slug,name,model,variants}`, `ProductVariant{id,color,price:Decimal,cost:Decimal}`; `eq=False` + explicit id-based `__eq__`/`__hash__`; slug regex+length; money validation (Decimal type, finite, non-negative, scale<=2) |
| `backend/src/gcell/products/application/repository.py` | Modified | `ProductRepository` Protocol fully async; `get_by_name` replaced by `get_by_id`+`get_by_slug` |
| `backend/src/gcell/products/application/exceptions.py` | Created | `DuplicateProductSlugError(slug)` |
| `backend/src/gcell/products/application/register_product.py` | Modified | `execute` is now `async`; pre-check removed, relies on `repository.add` |
| `backend/src/gcell/products/infrastructure/in_memory_product_repository.py` | Modified | Async; `dict[UUID, Product]` + `dict[str, UUID]` slug index; raises `DuplicateProductSlugError` |
| `backend/tests/unit/products/test_product_domain.py` | Modified | New shape fixtures (`id`, `color`, `Decimal` price/cost, `slug`/`model`); 17 tests covering id-equality, slug format/length, money invariants (type/finite/non-negative/scale) |
| `backend/tests/unit/products/test_register_product_use_case.py` | Modified | Async tests; `get_by_slug`/`get_by_id`; `DuplicateProductSlugError` on slug collision; zero-variant registration |
| `openspec/changes/products-postgres-adapter/tasks.md` | Modified | Phase 1 tasks 1.1-1.7 marked `[x]` |

### TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|------|-----------|-------|------------|-----|-------|-------------|----------|
| 1.1/1.2 | `backend/tests/unit/products/test_product_domain.py` | Unit | ✅ 9/9 (baseline full suite) | ✅ Written — 15/17 failed against old `product.py` shape | ✅ 17/17 passed after rewrite | ✅ id-equality (2 cases), slug format/length (3 cases), money type/finite/negative/scale (6 cases) | ✅ Clean — shared `_validate_money` helper avoids duplicating 4 checks across price/cost |
| 1.3-1.7 | `backend/tests/unit/products/test_register_product_use_case.py` | Unit | ✅ 17/17 (post 1.1/1.2) | ✅ Written — collection error (`ModuleNotFoundError: gcell.products.application.exceptions`) against old sync/`get_by_name` shape | ✅ 5/5 passed after `exceptions.py`, async `repository.py`, async `register_product.py`, async `in_memory_product_repository.py` | ✅ duplicate-slug rejection, zero-variant registration, get_by_id round-trip, get_by_slug unknown->None | ✅ Clean — no dead code, docstrings note the design rationale (TOCTOU avoidance) |

### Test Summary
- **Total tests written/updated**: 22 (17 domain + 5 use-case/repository)
- **Total tests passing**: 24/24 full backend suite (`pytest backend/tests -q`)
- **Layers used**: Unit (22 in products), plus 2 pre-existing (health API, architecture boundary) unaffected
- **Approval tests**: None — no refactoring-only tasks in this batch, only spec-driven behavior changes
- **Pure functions created**: `_validate_money(field_name, value)` in `product.py`

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `uv run --project backend pytest backend/tests/unit/products -q` -> `22 passed` |
| Runtime harness command/scenario and exact result | N/A — pure Python domain + in-memory adapter, no DB boundary in this PR |
| Rollback boundary | Revert `backend/src/gcell/products/domain/product.py`, `backend/src/gcell/products/application/{repository.py,register_product.py,exceptions.py}`, `backend/src/gcell/products/infrastructure/in_memory_product_repository.py`, `backend/tests/unit/products/*.py` |

Also ran full suite: `uv run --project backend pytest backend/tests -q` -> `24 passed` (includes `test_health.py` and `test_domain_boundary.py`, both untouched and green — `products/domain/product.py` still imports only `re`/`dataclasses`/`decimal`/`uuid`, stdlib only).
`ruff check backend/src/gcell/products backend/tests/unit/products` -> `All checks passed!`

### Deviations from Design
None — implementation matches `design.md`'s "identity, equality, and money invariants" and "duplicate slug via constraint translation" decisions exactly, scoped to the in-memory adapter (Postgres constraint translation is PR2's job per the task split).

One spec/design tension resolved in favor of design (authoritative for HOW): the spec's Requirement text says `ProductVariant` should carry "a reference to its parent product's id," but design's exact `Interfaces / Contracts` section states "`ProductVariant` carries no `product_id`: the adapter derives it from the root" — followed design, since PR2's Postgres adapter is the layer that owns the `product_id` foreign key column, not the domain model.

### Issues Found
None.

### Workload / PR Boundary
- Mode: stacked-to-main chained PR slice (PR1 of 3)
- Current work unit: Work Unit 1 — "Domain realignment: id/slug/model/Decimal on Product+Variant, async in-memory port"
- Boundary: starts from `main` (post `supabase-schema` archive), ends at Phase 1 tasks 1.1-1.7 complete — Phase 2 (Postgres adapter, `asyncpg`, `shared/infrastructure`) and Phase 3 (stock domain) are separate PRs not started
- Estimated review budget impact: within the "Domain realignment" work unit's forecasted line count; no DB dependency added in this slice

### Remaining Tasks (Phase 2 and Phase 3, separate PRs — not this batch)
- [ ] 2.1-2.9 Products Postgres Adapter (PR2)
- [ ] 3.1-3.11 Stock Domain (PR3)
- [ ] 4.1-4.3 Verification (after PR2/PR3 land)

### Status
7/7 Phase 1 tasks complete. Ready for sdd-verify on this PR1 slice.

## Batch: PR2 — Phase 2 Products Postgres Adapter

**Branch**: `pr2-products-postgres-repo` (branched from `main`, which already
has PR1's domain realignment merged)
**Mode**: Strict TDD
**Scope**: Phase 2 tasks only (2.1-2.9). Phase 3 (stock domain) is a
separate PR, NOT touched in this batch. Docker Desktop + local Supabase were
running throughout (`DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres`),
so every integration test below ran against real Postgres, not mocks.

### Completed Tasks (9/9 in Phase 2)

- [x] 2.1 [GREEN] Created `shared/infrastructure/config.py`: `db_url()` from `os.environ`
- [x] 2.2 [GREEN] Created `shared/infrastructure/postgres.py`: `create_pool`, `close_pool`, `transaction(pool_or_conn)` accepting `Pool` or `Connection` (nested `Connection.transaction()` becomes a SAVEPOINT)
- [x] 2.3 [GREEN] Updated `main.py`: `lifespan` -> `app.state.db_pool`, `min_size=0`, missing `DB_URL` -> warn + `None`
- [x] 2.4 [RED->GREEN] Fixed `test_health.py`: `with TestClient(app) as client:` so lifespan actually runs
- [x] 2.5 [GREEN] Added `asyncpg` to `backend/pyproject.toml` (`uv sync` installed `asyncpg==0.31.0`); created `backend/.env.example`
- [x] 2.6 [GREEN] Created `backend/tests/conftest.py`: `db_pool` (skip if no `DB_URL`), `db_conn` (rollback-isolated per test)
- [x] 2.7 [RED] Created `tests/integration/db/test_product_repository.py`: round-trip by slug/id incl. zero-variant, Decimal-scale-2 round-trip, duplicate slug -> `DuplicateProductSlugError` (+ no new row), failed insert leaves no rows, `list_all` mixes with/without-variant products
- [x] 2.8 [GREEN] Created `products/infrastructure/postgres_product_repository.py`: client `uuid4()` before insert, atomic `INSERT products` + `executemany` variants (wrapped in the shared `transaction()` helper so a `Connection` nests as a SAVEPOINT), one `LEFT JOIN` read grouped in the adapter, `UniqueViolationError` scoped to `products_slug_key` -> `DuplicateProductSlugError`
- [x] 2.9 [GREEN] Added `"asyncpg"` to `BANNED_MODULES` in `test_domain_boundary.py` (defer `application/` sweep — per notes, out of scope for this change)

Two extra RED-first behaviors were added beyond the 9 tasks, per the
orchestrator's explicit strict-TDD instruction to prove `transaction()` and
the pool lifespan directly (tasks.md scopes the *files*, not every test):
- `tests/integration/db/test_postgres_transaction.py` — exercises both
  branches of `transaction()` directly: `Pool` (real BEGIN/COMMIT and
  BEGIN/ROLLBACK, with manual cleanup since these commits aren't protected
  by `db_conn`'s outer rollback) and `Connection` (nested SAVEPOINT).
- `tests/integration/api/test_lifespan.py` — `app.state.db_pool` is `None`
  when `DB_URL` is unset, and a real, open-then-closed `asyncpg.Pool` when
  it is set (checked via the public `pool.is_closing()`, not the private
  `_closed` attribute).

### Files Changed

| File | Action | What Was Done |
|------|--------|----------------|
| `backend/pyproject.toml` | Modified | Added `asyncpg>=0.30.0` runtime dependency |
| `backend/.env.example` | Created | `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres` (local Docker credential only, `.env` stays gitignored) |
| `backend/src/gcell/shared/infrastructure/config.py` | Created | `db_url()` reads `os.environ.get("DB_URL")`, no dotenv dependency |
| `backend/src/gcell/shared/infrastructure/postgres.py` | Created | `create_pool(dsn)` (`min_size=0, max_size=10`), `close_pool(pool)`, `transaction(pool_or_conn)` async context manager branching on `isinstance(..., asyncpg.Pool)` |
| `backend/src/gcell/main.py` | Modified | `@asynccontextmanager lifespan(app)` sets `app.state.db_pool` (pool or `None` + warning log), closes it on shutdown; `FastAPI(..., lifespan=lifespan)` |
| `backend/src/gcell/products/infrastructure/postgres_product_repository.py` | Created | `PostgresProductRepository(conn)`: `add`/`get_by_id`/`get_by_slug`/`list_all`; client-generated `uuid4()`; `UniqueViolationError` on `products_slug_key` -> `DuplicateProductSlugError`; LEFT JOIN read grouped by product id, zero-variant-safe |
| `backend/tests/architecture/test_domain_boundary.py` | Modified | `BANNED_MODULES` gained `"asyncpg"` |
| `backend/tests/integration/api/test_health.py` | Modified | `with TestClient(app) as client:` so lifespan runs |
| `backend/tests/integration/api/test_lifespan.py` | Created | `db_pool` is `None` without `DB_URL`; real pool created+closed with `DB_URL` |
| `backend/tests/integration/db/test_postgres_transaction.py` | Created | `transaction()` Pool-branch commit/rollback + Connection-branch SAVEPOINT |
| `backend/tests/integration/db/test_product_repository.py` | Created | 10 tests: round-trip by slug/id, Decimal scale-2, zero-variant, unknown slug/id, duplicate slug (+row-count proof), atomic-failure (+row-count proof), `list_all` |
| `backend/tests/unit/shared/test_config.py` | Created | `db_url()` set/unset |
| `backend/tests/conftest.py` | Created | `db_pool` (function-scoped, skips without `DB_URL`), `db_conn` (rollback-isolated) |
| `openspec/changes/products-postgres-adapter/tasks.md` | Modified | Phase 2 tasks 2.1-2.9 marked `[x]` |

### TDD Cycle Evidence

| Task | Test File | Layer | RED | GREEN |
|------|-----------|-------|-----|-------|
| 2.1 | `test_config.py` | Unit | ✅ `ModuleNotFoundError: gcell.shared.infrastructure.config` | ✅ 2/2 passed |
| 2.2 | `test_postgres_transaction.py` | Integration (DB) | ✅ `ModuleNotFoundError: gcell.shared.infrastructure.postgres` | ✅ 3/3 passed (Pool commit, Pool rollback, Connection SAVEPOINT) |
| 2.3/2.4 | `test_health.py` + `test_lifespan.py` | Integration (API) | ✅ `AttributeError: 'State' object has no attribute 'db_pool'` (2 lifespan tests failed; `test_health` alone stayed green since `/health` never touches the pool) | ✅ 3/3 passed |
| 2.7/2.8 | `test_product_repository.py` | Integration (DB) | ✅ `ModuleNotFoundError: gcell.products.infrastructure.postgres_product_repository` | ✅ 10/10 passed |
| 2.9 | `test_domain_boundary.py` | Architecture | N/A — data-only list addition, no red state possible (nothing in `domain/` imports `asyncpg`) | ✅ 1/1 passed |

### Test Summary
- **Total tests written**: 18 new (2 config + 3 transaction-helper + 2 lifespan + 10 repository + 1 fixed `test_health.py`)
- **Total tests passing without `DB_URL`**: 28 passed, 13 skipped (`pytest backend/tests -q`) — all DB-touching tests skip cleanly, unit suite stays green with zero Postgres dependency
- **Total tests passing with `DB_URL` set to local Supabase**: 41 passed, 0 skipped, 0 failed (`pytest backend/tests -q`)
- **Layers used**: Unit (`shared/config`), Integration/API (`lifespan`, `health`), Integration/DB (`transaction()`, `PostgresProductRepository`), Architecture (`domain_boundary`)
- **Real-DB verification**: manually queried `products` table after the full suite run — row count unchanged from pre-existing seed data (`fundas-iphone-15`, `fundas-galaxy-s24`), confirming `db_conn`'s per-test rollback and the pool-branch tests' manual cleanup both leave zero residue

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run --project backend pytest backend/tests/integration/db/test_product_repository.py backend/tests/integration/api/test_health.py -q` -> `12 passed` |
| Runtime harness command/scenario and exact result | `npx supabase status` confirmed reachable local Postgres; full suite `DB_URL=... uv run --project backend pytest backend/tests -q` -> `41 passed` |
| Rollback boundary | Revert `backend/src/gcell/shared/infrastructure/{config.py,postgres.py}`, `backend/src/gcell/main.py`, `backend/src/gcell/products/infrastructure/postgres_product_repository.py`, `backend/pyproject.toml`'s `asyncpg` dep, `backend/.env.example`, `backend/tests/conftest.py`, `backend/tests/integration/db/*.py`, `backend/tests/integration/api/{test_health.py,test_lifespan.py}`, `backend/tests/unit/shared/*.py`, `backend/tests/architecture/test_domain_boundary.py`'s `BANNED_MODULES` entry |

`ruff check backend/src backend/tests` -> `All checks passed!`

### Deviations from Design
None in substance. One addition beyond design's explicit `File Changes`
table: design mentions an `Executor` protocol for `postgres.py` in its file
table, but no interface/contract section defines its shape and no Phase 2
task calls for it, so it was not created — `transaction()`'s parameter is
typed directly as `asyncpg.Pool | asyncpg.Connection`, which is sufficient
for this PR's actual call sites (`PostgresProductRepository` always receives
a `Connection`; nothing yet receives a bare `Pool` in production code except
the lifespan itself). This can be introduced in PR3 if `stock/`'s adapters
need a narrower duck-typed protocol.

Two RED-first tests were added beyond the 9 formally listed tasks
(`test_postgres_transaction.py`, `test_lifespan.py`) per this batch's
explicit strict-TDD instruction that `transaction()` and the pool lifespan
each get their own RED-first proof, not just indirect coverage through the
product-repository tests.

### Issues Found
None. The architecture test's `asyncpg` ban required no source changes —
`postgres_product_repository.py` and `postgres.py` both live in
`infrastructure/`, never `domain/`, so the boundary was clean by construction.

### Workload / PR Boundary
- Mode: stacked-to-main chained PR slice (PR2 of 3)
- Current work unit: Work Unit 2 — "Products Postgres adapter + pool lifespan"
- Boundary: starts from `main` (post PR1 merge), ends at Phase 2 tasks 2.1-2.9
  complete — Phase 3 (stock domain) is a separate PR, not started, and will
  branch from this branch after it merges
- Estimated review budget impact: within the "Products Postgres adapter"
  work unit's forecasted line count

### Remaining Tasks (Phase 3 and Phase 4, separate PR/verification — not this batch)
- [ ] 3.1-3.11 Stock Domain (PR3)
- [ ] 4.1-4.3 Verification (after PR3 lands)

### Status
9/9 Phase 2 tasks complete. Ready for sdd-verify on this PR2 slice.

## Batch: PR3 — Phase 3 Stock Domain + Phase 4 Verification

**Branch**: `pr3-stock-domain` (branched from `main`, which already has PR1's
domain realignment AND PR2's Postgres adapter merged)
**Mode**: Strict TDD
**Scope**: Phase 3 tasks (3.1-3.11, stock domain) + Phase 4 tasks (4.1-4.3,
cross-cutting verification). This is the final slice of the
`products-postgres-adapter` change — after this merges the whole change is
apply-complete. Docker Desktop + local Supabase were running throughout
(`DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres`), so every
integration test below ran against real Postgres, not mocks.

### Completed Tasks (11/11 Phase 3 + 3/3 Phase 4)

- [x] 3.1 [RED] Created `tests/unit/stock/test_stock_movement_domain.py`: sign-direction per `MovementType` (all 5 types), non-zero delta, blank-reason rejected, immutability (`FrozenInstanceError`), value-based equality
- [x] 3.2 [GREEN] Created `stock/domain/stock_movement.py`: `MovementType` StrEnum (`restock`/`sale`/`return`/`breakage`/`adjustment`), `@dataclass(frozen=True) StockMovement`, `__post_init__` mirrors `stock_movements_sign_direction_check` exactly
- [x] 3.3 [GREEN] Created `stock/application/repository.py`: `StockMovementRepository` Protocol with exactly one method, `record(movement) -> None` — RED-first port-shape test (`vars(StockMovementRepository)` public members == `{"record"}`) proves no update/delete can be added silently
- [x] 3.4 [GREEN] Created `stock/application/stock_level_reader.py`: `StockLevelReader.quantity_on_hand(variant_id)`; `stock/application/exceptions.py`: `UnknownVariantError` — both RED-first with their own tests
- [x] 3.5 [RED] Created `tests/unit/stock/test_record_stock_movement_use_case.py`: valid movement recorded, unknown type and wrong-sign rejected before persistence (proved via `repository.recorded == []` after the raise)
- [x] 3.6 [GREEN] Created `stock/application/record_stock_movement.py`: `RecordStockMovementUseCase`, `str -> MovementType` (`ValueError` on unknown) resolved BEFORE constructing the entity; plus `stock/infrastructure/in_memory_stock_movement_repository.py` and `in_memory_stock_level_reader.py` test-double adapters
- [x] 3.7 [RED] Created `tests/unit/stock/test_register_stocked_product_use_case.py`: orchestrates `ProductRepository` + `StockMovementRepository`, zero-stock registration succeeds (empty `initial_movements` default), multiple initial movements all recorded in order
- [x] 3.8 [GREEN] Created `stock/application/register_stocked_product.py`: `RegisterStockedProductUseCase(products, movements)`, `execute(product, initial_movements=())`
- [x] 3.9 [RED] Created `tests/integration/db/test_stock_movement_repository.py`: insert-only row persistence, `variant_stock_levels` sum via `PostgresStockLevelReader` matches recorded movements (+10 restock, -3 sale = 7), zero-movement variant reads 0, unknown-variant FK violation -> `UnknownVariantError` (+ zero-row proof), direct `UPDATE` against `stock_movements` rejected by the DB trigger
- [x] 3.10 [GREEN] Created `stock/infrastructure/postgres_stock_movement_repository.py` (`record`, FK-violation translation scoped to `stock_movements_variant_id_fkey`, wrapped in the shared `transaction()` helper as a SAVEPOINT so a caller's enclosing transaction survives the failure) and `postgres_stock_level_reader.py` (`quantity_on_hand` via `coalesce(...,0)` over `variant_stock_levels`)
- [x] 3.11 [RED->GREEN] Created `tests/integration/db/test_register_stocked_product_atomicity.py`: (a) successful registration commits product+variant+movement together (via `db_conn`/SAVEPOINT — see Deviations), (b) a failing second movement (unknown `variant_id`) after a successful first movement leaves ZERO rows in `products`, `product_variants`, AND `stock_movements` — driven through a real `transaction(pool)` BEGIN/ROLLBACK on `db_pool`
- [x] 4.1 Confirmed `npx supabase status` reachable (local Docker Supabase already running for the whole session; `DB_URL` resolved from `npx supabase status`'s own output)
- [x] 4.2 Ran full `pytest backend/tests -q`: **without `DB_URL`** -> `54 passed, 20 skipped` (all DB-touching tests skip cleanly, unit suite has zero Postgres dependency); **with `DB_URL` set** -> `74 passed, 0 skipped, 0 failed`
- [x] 4.3 Confirmed `test_domain_boundary.py` passes with `asyncpg` banned in every domain's `domain/` layer — **zero further edits needed**, exactly as predicted: `"stock"` was already in `DOMAINS` (PR1) and `"asyncpg"` was already in `BANNED_MODULES` (PR2), so `stock/domain/stock_movement.py` was covered by construction the moment it existed. Also manually verified the `stock -> products` dependency direction: `grep` for `gcell.stock` imports inside `products/` found zero matches; `grep` for `gcell.products` imports inside `stock/` found exactly one file, `register_stocked_product.py` (the legal direction).

### Files Changed

| File | Action | What Was Done |
|------|--------|----------------|
| `backend/src/gcell/stock/domain/stock_movement.py` | Created | `MovementType` StrEnum; `StockMovement` frozen dataclass; `__post_init__` enforces non-zero delta, sign-direction per type, non-blank `reason` |
| `backend/src/gcell/stock/application/repository.py` | Created | `StockMovementRepository` Protocol — exactly one method, `record` |
| `backend/src/gcell/stock/application/stock_level_reader.py` | Created | `StockLevelReader` Protocol — exactly one method, `quantity_on_hand` |
| `backend/src/gcell/stock/application/exceptions.py` | Created | `UnknownVariantError(variant_id)` |
| `backend/src/gcell/stock/application/record_stock_movement.py` | Created | `RecordStockMovementUseCase`: str->enum resolution, entity construction, `repository.record` |
| `backend/src/gcell/stock/application/register_stocked_product.py` | Created | `RegisterStockedProductUseCase`: orchestrates `ProductRepository.add` + `StockMovementRepository.record` per initial movement; no transaction ownership (caller-owned) |
| `backend/src/gcell/stock/infrastructure/in_memory_stock_movement_repository.py` | Created | `InMemoryStockMovementRepository` — `recorded: list[StockMovement]` |
| `backend/src/gcell/stock/infrastructure/in_memory_stock_level_reader.py` | Created | `InMemoryStockLevelReader` — sums an in-memory movement list per `variant_id` |
| `backend/src/gcell/stock/infrastructure/postgres_stock_movement_repository.py` | Created | `PostgresStockMovementRepository(conn).record`; `ForeignKeyViolationError` on `stock_movements_variant_id_fkey` -> `UnknownVariantError`; INSERT wrapped in `transaction(self._conn)` (SAVEPOINT) so a caller's enclosing transaction survives a translated failure |
| `backend/src/gcell/stock/infrastructure/postgres_stock_level_reader.py` | Created | `PostgresStockLevelReader(conn).quantity_on_hand` via `coalesce((SELECT ... FROM variant_stock_levels WHERE variant_id=$1), 0)` |
| `backend/tests/unit/stock/test_stock_movement_domain.py` | Created | 16 tests: sign-direction (all 5 types x correct/incorrect sign), zero-delta rejection, reason blank/present/default, immutability, value equality |
| `backend/tests/unit/stock/test_stock_movement_repository_port.py` | Created | Port-shape proof: public members == `{"record"}` |
| `backend/tests/unit/stock/test_stock_level_reader_port.py` | Created | Port-shape proof: public members == `{"quantity_on_hand"}` |
| `backend/tests/unit/stock/test_stock_exceptions.py` | Created | `UnknownVariantError` carries `variant_id`, message contains it |
| `backend/tests/unit/stock/test_record_stock_movement_use_case.py` | Created | 4 tests: valid record, unknown type rejected pre-persistence, wrong-sign rejected pre-persistence, optional `reason` |
| `backend/tests/unit/stock/test_register_stocked_product_use_case.py` | Created | 3 tests: zero-stock succeeds with no movements recorded, single initial movement recorded, multiple initial movements recorded in order |
| `backend/tests/integration/db/test_stock_movement_repository.py` | Created | 5 tests: row persistence, ledger-sum-matches-reader, zero-movement variant reads 0, unknown-variant FK->`UnknownVariantError` (+zero-row proof), direct `UPDATE` rejected by trigger |
| `backend/tests/integration/db/test_register_stocked_product_atomicity.py` | Created | 2 tests: successful cross-domain commit (via `db_conn` SAVEPOINT), failed second movement leaves zero rows across `products`/`product_variants`/`stock_movements` (via real `transaction(db_pool)` BEGIN/ROLLBACK) |
| `openspec/changes/products-postgres-adapter/tasks.md` | Modified | Phase 3 tasks 3.1-3.11 and Phase 4 tasks 4.1-4.3 marked `[x]`; Notes item 4 added documenting the append-only cleanup constraint discovery |

### TDD Cycle Evidence

| Task | Test File | Layer | RED | GREEN |
|------|-----------|-------|-----|-------|
| 3.1/3.2 | `test_stock_movement_domain.py` | Unit | ✅ `ModuleNotFoundError: gcell.stock.domain.stock_movement` | ✅ 16/16 passed |
| 3.3 | `test_stock_movement_repository_port.py` | Unit | ✅ `ModuleNotFoundError: gcell.stock.application.repository` | ✅ 1/1 passed |
| 3.4 | `test_stock_level_reader_port.py` + `test_stock_exceptions.py` | Unit | ✅ both `ModuleNotFoundError` | ✅ 2/2 passed |
| 3.5/3.6 | `test_record_stock_movement_use_case.py` | Unit | ✅ `ModuleNotFoundError: gcell.stock.application.record_stock_movement` | ✅ 4/4 passed |
| 3.7/3.8 | `test_register_stocked_product_use_case.py` | Unit | ✅ `ModuleNotFoundError: gcell.stock.application.register_stocked_product` | ✅ 3/3 passed |
| 3.9/3.10 | `test_stock_movement_repository.py` | Integration (DB) | ✅ `ModuleNotFoundError: gcell.stock.infrastructure.postgres_stock_level_reader` | ✅ 5/5 passed (one intermediate failure fixed mid-cycle — see Issues Found) |
| 3.11 | `test_register_stocked_product_atomicity.py` | Integration (DB) | ✅ written against fully-existing infra (no new production code needed); first run failed on cleanup (see Issues Found), not on the assertions | ✅ 2/2 passed after harness fix |

### Test Summary
- **Total tests written**: 33 new — `pytest backend/tests/unit/stock -q` -> `26 passed` (16 domain + 1 repo-port-shape + 1 reader-port-shape + 1 exception + 4 record-use-case + 3 register-use-case), `pytest backend/tests/integration/db/test_stock_movement_repository.py backend/tests/integration/db/test_register_stocked_product_atomicity.py -q` -> `7 passed` (5 repository/reader + 2 atomicity)
- **Total tests passing without `DB_URL`**: `54 passed, 20 skipped` (full `backend/tests`)
- **Total tests passing with `DB_URL` set to local Supabase**: `74 passed, 0 skipped, 0 failed` (full `backend/tests`)
- **Layers used**: Unit (domain invariants, port shapes, use cases with in-memory doubles), Integration/DB (Postgres adapters, cross-domain atomicity), Architecture (`domain_boundary`, unchanged)
- **Approval tests**: None — no refactoring-only tasks in this batch
- **Pure functions created**: `StockMovement.__post_init__`'s sign-direction check (data-driven via `_POSITIVE_ONLY`/`_NEGATIVE_ONLY` frozensets, no branching duplication across the 5 movement types)

### Work Unit Evidence

| Evidence | Value |
|---|---|
| Focused test command and exact result | `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres uv run --project backend pytest backend/tests/unit/stock backend/tests/integration/db/test_stock_movement_repository.py backend/tests/integration/db/test_register_stocked_product_atomicity.py -q` -> `33 passed` |
| Runtime harness command/scenario and exact result | `npx supabase status` confirmed reachable local Postgres; full suite `DB_URL=... uv run --project backend pytest backend/tests -q` -> `74 passed, 0 skipped, 0 failed` |
| Rollback boundary | Revert `backend/src/gcell/stock/` tree entirely (domain/application/infrastructure), `backend/tests/unit/stock/`, `backend/tests/integration/db/test_stock_movement_repository.py`, `backend/tests/integration/db/test_register_stocked_product_atomicity.py` — depends only on PR1/PR2's `ProductRepository` port and `transaction()` helper, zero edits to `products/` or `shared/` source in this batch |

`ruff check backend/src backend/tests` -> `All checks passed!`

### Deviations from Design

1. **`test_register_stocked_product_atomicity.py`'s success-path harness**: design/tasks implied driving BOTH the success and failure scenarios "through `transaction(pool)`" with a real Pool-level commit. Mid-apply, discovered `stock_movements` is append-only even for a superuser connection (`BEFORE UPDATE OR DELETE` trigger, unconditional) AND `variant_id` has `ON DELETE RESTRICT` from `product_variants` — so a genuinely COMMITTED movement row has **no valid cleanup statement** (`DELETE`/`UPDATE` both rejected by the trigger; the referencing variant/product can't be deleted either because of the RESTRICT FK). Attempting `db_pool` + manual `DELETE` cleanup for the success test failed with `RaiseError: stock_movements is append-only: DELETE is not permitted`. Fixed by using `db_conn` (SAVEPOINT via nested `transaction(db_conn)`) for the success-path test instead — this still exercises the exact same `RegisterStockedProductUseCase` + shared-connection pattern and proves cross-domain commit correctness, while `db_conn`'s teardown is a plain `ROLLBACK` (transaction control, not a DML statement), so the append-only trigger never fires and zero rows survive. The REQUIRED spec scenario ("Failure leaves no partial rows") still uses a genuine `transaction(db_pool)` BEGIN/ROLLBACK, since a rolled-back transaction commits nothing and needs no cleanup at all. The Pool-branch's real BEGIN/COMMIT mechanics are already proven generically and independently by PR2's `test_postgres_transaction.py::test_transaction_with_pool_commits_on_clean_exit`. Documented as Notes item 4 in `tasks.md`.
2. **`PostgresStockMovementRepository.record` wraps its INSERT in `transaction(self._conn)`** (a detail not spelled out in design's SQL section, but required by the same principle design already established for `PostgresProductRepository.add`): a failed statement aborts Postgres's ENTIRE enclosing transaction, so without the nested SAVEPOINT, a caller's `db_conn` (or a composition root's already-open transaction) would become unusable for any further statement after a translated `UnknownVariantError` — confirmed by an `InFailedSQLTransactionError` on the very first attempt at the unknown-variant integration test, fixed by mirroring the products adapter's existing pattern exactly.

No other deviations — `StockMovement`, `StockMovementRepository`, `StockLevelReader`, `RecordStockMovementUseCase`, and `RegisterStockedProductUseCase` all match design's `Interfaces / Contracts` section exactly, including `record(movement) -> None` (not `-> StockMovement`/id-returning, since `stock_movements.id` is DB-assigned and never consumed by any port caller in this change).

### Issues Found

1. First run of `test_stock_movement_repository.py::test_record_against_unknown_variant_raises_unknown_variant_error` failed with `InFailedSQLTransactionError` on its own follow-up verification query — root-caused to the missing SAVEPOINT wrap described in Deviations item 2 above, fixed immediately, not a pre-existing failure.
2. First run of `test_register_stocked_product_atomicity.py`'s success-path test failed its `finally`-block cleanup with `RaiseError: stock_movements is append-only: DELETE is not permitted` — root-caused to the append-only trigger + RESTRICT FK combination described in Deviations item 1 above, fixed by switching the harness from `db_pool`+manual-cleanup to `db_conn`+SAVEPOINT.

Both were caught and fixed within this same batch before marking the tasks complete — no residual test-DB pollution from either failed first attempt (the FK-violation attempt never inserted a row in the first place; the cleanup-failure attempt's product/variant/movement rows are erased by `db_conn`'s fixture-level `ROLLBACK` regardless of the mid-test `DELETE` failure, since `ROLLBACK` discards the whole transaction unconditionally).

### Workload / PR Boundary
- Mode: stacked-to-main chained PR slice (PR3 of 3 — FINAL slice)
- Current work unit: Work Unit 3 — "Stock domain: movement, use cases, Postgres adapters"
- Boundary: starts from `main` (post PR1+PR2 merge), ends at Phase 3 tasks 3.1-3.11 AND Phase 4 tasks 4.1-4.3 complete — nothing remains in this change after this slice merges
- Estimated review budget impact: within the "Stock domain" work unit's forecasted line count; zero edits to `products/` or `shared/` source (only new `stock/` files + new tests), keeping the diff focused per the chain strategy

### Remaining Tasks
None. All 26 tasks across Phase 1-4 are complete (`1.1`-`1.7`, `2.1`-`2.9`, `3.1`-`3.11`, `4.1`-`4.3`).

### Status
11/11 Phase 3 tasks + 3/3 Phase 4 tasks complete (26/26 total across the whole
`products-postgres-adapter` change). Ready for `sdd-verify` on this PR3 slice
— and, once PR3 merges to `main`, the whole change is apply-complete and
ready for a change-level `sdd-verify` pass.
