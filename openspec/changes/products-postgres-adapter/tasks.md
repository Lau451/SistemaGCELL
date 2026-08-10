# Tasks: products-postgres-adapter

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1000-1200 (production ~550, tests ~500) across ~26 files |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 domain realignment -> PR2 products Postgres adapter -> PR3 stock domain |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main (cached at session preflight) |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Domain realignment: id/slug/model/Decimal on Product+Variant, async in-memory port | PR 1 | `pytest backend/tests/unit/products -q` | N/A — pure Python, no DB | Revert `products/domain`, `products/application`, `products/infrastructure/in_memory_*`, unit tests |
| 2 | Products Postgres adapter + pool lifespan | PR 2 | `pytest backend/tests/integration/db/test_product_repository.py backend/tests/integration/api/test_health.py -q` | `npx supabase status` reachable local Postgres, `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres` | Revert `shared/infrastructure`, `main.py` lifespan, `postgres_product_repository.py` |
| 3 | Stock domain: movement, use cases, Postgres adapters | PR 3 | `pytest backend/tests/unit/stock backend/tests/integration/db/test_stock_movement_repository.py backend/tests/integration/db/test_register_stocked_product_atomicity.py -q` | Same local Postgres as PR2 | Revert `stock/` tree entirely — depends only on PR1/PR2's `ProductRepository` port |

## Phase 1: Domain Realignment (PR1)

- [x] 1.1 [RED] Rewrite `test_product_domain.py`: id-based eq/hash, Decimal price/cost, slug/model/color invariants
- [x] 1.2 [GREEN] Rewrite `products/domain/product.py`: `@dataclass(eq=False)` `Product{id,slug,name,model,variants}` / `ProductVariant{id,color,price:Decimal,cost:Decimal}`; explicit `__eq__`/`__hash__` on `id`; slug regex+length, Decimal-type/finite/`>=0`/scale-2 checks
- [x] 1.3 [RED] Update `test_register_product_use_case.py` for async `execute`
- [x] 1.4 [GREEN] Make `products/application/repository.py` async: `add`/`get_by_id`/`get_by_slug`/`list_all`, drop `get_by_name`
- [x] 1.5 [GREEN] Create `products/application/exceptions.py`: `DuplicateProductSlugError`
- [x] 1.6 [GREEN] Update `register_product.py`: async, remove `get_by_slug` pre-check (constraint translation moves to infra)
- [x] 1.7 [GREEN] Update `in_memory_product_repository.py`: async, id-keyed dict + slug index, raises `DuplicateProductSlugError`

## Phase 2: Products Postgres Adapter (PR2)

- [ ] 2.1 [GREEN] Create `shared/infrastructure/config.py`: `db_url()` from `os.environ`
- [ ] 2.2 [GREEN] Create `shared/infrastructure/postgres.py`: `create_pool`, `close_pool`, `transaction(pool_or_conn)` accepting Pool or Connection (nested `Connection.transaction()` becomes a SAVEPOINT)
- [ ] 2.3 [GREEN] Update `main.py`: `lifespan` -> `app.state.db_pool`, `min_size=0`, missing `DB_URL` -> warn + `None`
- [ ] 2.4 [RED->GREEN] Fix `test_health.py`: `with TestClient(app) as client:` so lifespan actually runs
- [ ] 2.5 [GREEN] Add `asyncpg` to `backend/pyproject.toml`; create `.env.example`
- [ ] 2.6 [GREEN] Create `backend/tests/conftest.py`: `db_pool` (skip if no `DB_URL`), `db_conn` (rollback-isolated per test)
- [ ] 2.7 [RED] Create `tests/integration/db/test_product_repository.py`: round-trip by slug/id incl. zero-variant, duplicate slug -> `DuplicateProductSlugError`, failed insert leaves no rows
- [ ] 2.8 [GREEN] Create `products/infrastructure/postgres_product_repository.py`: client `uuid4()` before insert, atomic INSERT products + `executemany` variants, one `LEFT JOIN` read, `UniqueViolationError` scoped to `products_slug_key` -> `DuplicateProductSlugError`
- [ ] 2.9 [GREEN] Add `"asyncpg"` to `BANNED_MODULES` in `test_domain_boundary.py` (defer `application/` sweep — see notes)

## Phase 3: Stock Domain (PR3)

- [ ] 3.1 [RED] Create `tests/unit/stock/test_stock_movement_domain.py`: sign-direction per `MovementType`, non-zero delta, blank-reason rejected
- [ ] 3.2 [GREEN] Create `stock/domain/stock_movement.py`: `MovementType` StrEnum, `@dataclass(frozen=True) StockMovement`, `__post_init__` mirrors `stock_movements_sign_direction_check`
- [ ] 3.3 [GREEN] Create `stock/application/repository.py`: `StockMovementRepository` Protocol with exactly one method, `record`
- [ ] 3.4 [GREEN] Create `stock/application/stock_level_reader.py`: `StockLevelReader.quantity_on_hand(variant_id)`; `stock/application/exceptions.py`: `UnknownVariantError`
- [ ] 3.5 [RED] Create `tests/unit/stock/test_record_stock_movement_use_case.py`: valid movement recorded, unknown type and wrong-sign rejected before persistence
- [ ] 3.6 [GREEN] Create `stock/application/record_stock_movement.py`: `RecordStockMovementUseCase`, str -> `MovementType` (`ValueError` on unknown), plus in-memory test-double repos
- [ ] 3.7 [RED] Create `tests/unit/stock/test_register_stocked_product_use_case.py`: orchestrates `ProductRepository` + `StockMovementRepository`, zero-stock registration succeeds
- [ ] 3.8 [GREEN] Create `stock/application/register_stocked_product.py`: `RegisterStockedProductUseCase`
- [ ] 3.9 [RED] Create `tests/integration/db/test_stock_movement_repository.py`: insert-only, ledger reflects movements, `variant_stock_levels` sum matches
- [ ] 3.10 [GREEN] Create `stock/infrastructure/postgres_stock_movement_repository.py` and `postgres_stock_level_reader.py`
- [ ] 3.11 [RED->GREEN] Create `tests/integration/db/test_register_stocked_product_atomicity.py`: failing second variant/movement leaves zero product/variant/movement rows, driven through `transaction(pool)`

## Phase 4: Verification

- [ ] 4.1 Confirm `npx supabase status` reachable (else `npx supabase start`) before running `backend/tests/integration/db`
- [ ] 4.2 Run full `pytest backend/tests -q`: unit suite green without `DB_URL`, integration suite green with local Postgres
- [ ] 4.3 Confirm `test_domain_boundary.py` passes with `asyncpg` banned in every domain's `domain/` layer

## Notes (Open Questions Resolved)

1. `application/` banned-import AST sweep: deferred, out of scope — spec only requires the `domain/` boundary; do not widen this change.
2. `Product.description`: not modeled — spec's Product fields are `id`/`slug`/`name`/`model` only; column stays nullable and unwritten.
3. `StockLevelReader` bulk read (`dict[UUID, int]`): confirmed out of scope — single-variant `quantity_on_hand` only, per design.
