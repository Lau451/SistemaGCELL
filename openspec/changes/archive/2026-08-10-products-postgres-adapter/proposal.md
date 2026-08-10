# Proposal: products-postgres-adapter

## Intent

Products and variants exist only in an in-memory dict. The real Postgres schema (`products`, `product_variants`, `stock_movements`, `variant_stock_levels`) has shipped since `supabase-schema`, but no backend code reaches it, so an admin cannot persist a product or adjust stock/cost. This change wires the admin/write path to real Postgres and delivers the first stock-ledger slice — the actual motivation for the change.

## Scope

### In Scope

- asyncpg pool + `PostgresProductRepository` (`add`, `get_by_id`, `get_by_slug`, `list_all`).
- Domain alignment: `Product(id, slug, name, model)`, `ProductVariant(id, color, price: Decimal, cost: Decimal)`. `phone_model` moves variant→product as `model`; money `float`→`Decimal` (matches `numeric(10,2)`; named target of archived `supabase-schema` design Decision #9); identity switches to id-based `__eq__`/`__hash__` (`eq=False`).
- Port `get_by_name`→`get_by_slug`, plus `get_by_id`. Fixes `RegisterProductUseCase`, whose duplicate check uses `name` while only `slug` is DB-unique — an in-scope correctness fix, not scope creep.
- `stock/` domain (not `products/`): `StockMovement`, `StockMovementRepository` port, `RecordStockMovementUseCase`, append-only Postgres adapter, derived stock read via `variant_stock_levels`. `stock/` depends on `products/`, never the reverse.
- Atomic product+variants(+initial movement) insert in one transaction.
- `main.py` lifespan for pool startup/shutdown; `test_health.py` becomes `with TestClient(app) as client:`.
- `asyncpg` added to `BANNED_MODULES` in `test_domain_boundary.py`.
- New `backend/.env.example` convention for `DB_URL` (local Docker Postgres superuser — a different credential from the Supabase `service_role` JWT, which this change does not use); loaded in `infrastructure/` only.
- pytest-asyncio tests against real local Postgres, per-test transaction rollback.

### Out of Scope

- Public catalog reads (`catalog_*` views, anon key, Next.js) — unchanged, separate path.
- `product_images` CRUD; product/variant update and delete (`ON DELETE RESTRICT` makes delete a separate design problem).
- Auth/authorization — leave a route-layer seam only.
- supabase-py/PostgREST; ORM or query builder.
- CI for DB-backed tests (known pre-existing gap).
- **Open**: admin HTTP routes — see question round below.

## Capabilities

### New Capabilities

- `product-persistence`: backend products domain model, repository port, and Postgres adapter for admin writes/reads.
- `stock-movement-recording`: recording append-only stock movements and reading derived per-variant stock.

### Modified Capabilities

- `platform-foundation`: backend boot now requires a DB connection-pool lifespan and `DB_URL` configuration; domain-boundary enforcement must ban the DB driver package.

## Approach

Direct asyncpg (settled): native `Decimal` for `numeric(10,2)`, real multi-statement transactions for atomic variant+movement inserts, no HTTP hop, clean FastAPI lifespan pooling. Domain stays driver-free; the adapter maps rows to entities and derives `product_id` from the aggregate root. Stock is written as ledger rows and read as a `SUM`, never as a mutable counter (a `BEFORE UPDATE OR DELETE` trigger forbids mutation for every role).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/src/gcell/products/domain/product.py` | Modified | `id`/`slug`/`model`/`color`, `Decimal` money, id-based equality |
| `backend/src/gcell/products/application/` | Modified | Port `get_by_slug`/`get_by_id`; slug-based duplicate check |
| `backend/src/gcell/products/infrastructure/` | New | `PostgresProductRepository`; in-memory adapter kept for unit tests |
| `backend/src/gcell/stock/` | New | Movement entity, port, use case, Postgres adapter |
| `backend/src/gcell/main.py` | Modified | Lifespan pool startup/shutdown |
| `backend/pyproject.toml` | Modified | `asyncpg` runtime dep |
| `backend/tests/` | Modified | DB fixtures, `TestClient` context manager, `BANNED_MODULES` |
| `backend/.env.example` | New | `DB_URL` convention |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `float`→`Decimal` breaks existing fixtures | High | Update fixtures in the same change; it is not additive |
| Medium scope may need rework when a full `stock` domain lands | Med | Accepted tradeoff; ledger port kept minimal and stock-owned |
| Lifespan makes DB mandatory for `/health` tests | Med | Context-managed `TestClient`; pool acquisition stays lazy |
| DB-backed tests need Docker/`supabase start` | High | Matches existing project convention; documented, CI noted as a gap |
| Superuser `DB_URL` bypasses RLS | Med | Intentional for a backend admin API; authorization belongs in the route layer later |

## Rollback Plan

Revert the change commits. The DB schema is untouched (no migrations added), so no data migration or down-migration is needed; recorded `stock_movements` rows simply remain as valid history. The in-memory repository stays in the tree, so reverting restores a working scaffold.

## Dependencies

- Local Supabase/Postgres running (`supabase start`) with `supabase-schema` migrations applied.
- New runtime dependency: `asyncpg`.

## Success Criteria

- [ ] A product with variants persists to Postgres and reads back by `slug` and `id` with `Decimal` money intact.
- [ ] Duplicate registration is rejected on `slug`, matching the DB unique constraint.
- [ ] A stock movement is recorded and derived stock via `variant_stock_levels` equals the movement sum.
- [ ] Product+variant+initial-movement insert is atomic (failure leaves no partial rows).
- [ ] `/health` still passes and the domain-boundary test bans `asyncpg`.
- [ ] Public catalog frontend behavior is unchanged.

## Proposal question round

Interactive pace, but this executor cannot prompt directly. Open product questions for user review:

1. Does this change deliver admin **HTTP routes** (e.g. `POST /admin/products`, `POST /admin/variants/{id}/movements`), or only domain/application/repository layers exercised by tests? Current assumption: **no routes** — repository and use-case layers only.
2. Which `movement_type` values must the first slice support (restock only, or the full CHECK-constrained enum)? Assumption: **all schema-allowed types**, validated in the domain.
3. Must product registration require an **initial stock movement**, or is a zero-stock product valid? Assumption: **optional** — zero stock is valid.
4. Is `slug` **caller-supplied** or derived from `name`? Assumption: **caller-supplied**, validated against the schema's format/length CHECK.
5. Should `ProductVariant` carry a read-only `quantity_on_hand` hydrated on read, or is stock read only through a separate stock query? Assumption: **separate stock query** — keeps `stock/` from leaking into the `products/` aggregate.
