# Design: products-postgres-adapter

## Technical Approach

Direct `asyncpg` behind unchanged hexagonal boundaries. `domain/` stays pure Python;
ports move to `async def` in `application/`; a Connection-scoped Postgres adapter per
domain lives in `infrastructure/`. A `shared/infrastructure/postgres.py` module owns the
pool, its FastAPI lifespan, and the single `transaction()` helper that makes the
cross-domain atomic write possible without leaking a driver type into any port.

No HTTP routes ship here. The pool is published on `app.state.db_pool` so the later
admin+auth change adds one `Depends` provider and nothing else.

## Architecture Decisions

### Decision: pool lifecycle and availability

**Choice**: `@asynccontextmanager lifespan(app)` in `main.py` → `app.state.db_pool`.
`asyncpg.create_pool(dsn, min_size=0, max_size=10)`; `await pool.close()` on shutdown.
If `DB_URL` is unset, log a warning and set `db_pool = None`.
Repositories receive a connection by **constructor injection**, never `Depends`.
**Alternatives**: module-level singleton (hidden global state, unswappable in tests);
a full `Depends` chain now (unused route infrastructure — over-building).
**Rationale**: `app.state` is Starlette's own lifespan handoff and is the exact seam a
future `get_pool(request)` provider reads. `min_size=0` means startup opens no socket, so
`/health` and unit tests never require Postgres. Tolerating a missing `DB_URL` is safe
**only because zero code paths consume the pool in this change**; the admin+auth change
MUST convert this to fail-fast or a 503 dependency guard.

### Decision: identity, equality, and money invariants

**Choice**: `@dataclass(eq=False)` + explicit `__eq__`/`__hash__` on `id` for `Product`
and `ProductVariant`. `@dataclass(frozen=True)` (value equality) for `StockMovement`.
**Alternatives**: `frozen=True` + `field(compare=False)` on every non-id field.
**Rationale**: `frozen` is shallow — `Product.variants` stays mutable, so the immutability
promise would be false; and `compare=False` noise on six fields is worse than six explicit
lines. A ledger row is genuinely immutable and DB-keyed (`bigint generated always as
identity`), so `frozen=True` with value equality is correct there and mirrors the
append-only trigger at the type level.
**Consequence (must propagate to tests)**: `read_back == written` is now trivially true on
`id` alone. DB round-trip tests MUST assert field-by-field (`price`, `cost`, `color`).

### Decision: duplicate slug via constraint translation, not pre-check

**Choice**: `PostgresProductRepository.add` catches `asyncpg.UniqueViolationError`, checks
`e.constraint_name == "products_slug_key"`, and raises
`DuplicateProductSlugError` (in `products/application/exceptions.py`). The
`get_by_slug` pre-check is **removed** from `RegisterProductUseCase`.
**Alternatives**: keep the pre-check (current pattern, but TOCTOU-racy, one extra round
trip, and duplicates the rule in two places).
**Rationale**: equal complexity (`try/except` vs `await` + `if`), so correctness wins even
at low stakes. The in-memory adapter raises the same exception type, so the use case is
adapter-agnostic. `ForeignKeyViolationError` on `stock_movements.variant_id` translates to
`UnknownVariantError` the same way. **Postgres aborts the whole transaction on a failed
statement**, so the translated exception MUST propagate out of the `transaction()` scope —
never caught and retried inside it.

### Decision: transaction boundary at the composition root, orchestration in a use case

**Choice**: `RegisterStockedProductUseCase` lives in `stock/application/` (legal direction:
`stock/ → products/`) and orchestrates `ProductRepository` + `StockMovementRepository` as
plain ports. The transaction is owned by the caller:

```python
async with transaction(pool) as conn:            # BEGIN
    await RegisterStockedProductUseCase(
        products=PostgresProductRepository(conn),
        movements=PostgresStockMovementRepository(conn),
    ).execute(product, initial_movements)
# COMMIT on clean exit; any raised exception → ROLLBACK
```

**Alternatives**: (a) a `UnitOfWork` port exposing both repos — a mini-container, and its
protocol has no legal home (`shared/` must not import `products/`); (b) `add(product, conn)`
— leaks `asyncpg` into the port signature; (c) products' repo writing `stock_movements` —
breaks the domain boundary outright.
**Rationale**: orchestrating multiple ports is an `application/` job; choosing *when* to
commit is an infrastructure job. Splitting them keeps the use case unit-testable against
in-memory repos with zero DB knowledge and lets the same use case run inside a larger
transaction later. `PostgresProductRepository` accepts a `Connection`, **not** a `Pool`, so
non-transactional use is impossible without deliberately calling `pool.acquire()` yourself;
an architecture test asserts `transaction()` is the only `acquire()` call site — the same
single-call-site guard the frontend uses for `catalogFrom`.

### Decision: append-only is a port-shape fact

**Choice**: `StockMovementRepository` has exactly one method, `record(movement) -> None`.
No `update`, no `delete`, no id-taking overload. Derived stock is read through a separate
`StockLevelReader` port (`quantity_on_hand(variant_id) -> int`).
**Alternatives**: a read method on the movements repo.
**Rationale**: mirrors `CatalogRelation` — the invariant is unwritable, not merely
unimplemented. `variant_stock_levels` is a *derived read model*, not the write entity;
keeping it on its own port stops callers treating the ledger as a mutable counter and lets
the migration's own "materialized rollup can replace this view" note land without touching
the write port.

### Decision: client-generated UUIDs and one LEFT JOIN read

**Choice**: `uuid4()` assigned at construction; `INSERT` supplies `id` explicitly. Reads use
a single `LEFT JOIN` grouped in the adapter.
**Alternatives**: DB `gen_random_uuid()` + `RETURNING id` (entity incomplete until after
insert — incompatible with id-based equality); two queries (extra round trip; inconsistent
outside a transaction).
**Rationale**: `LEFT JOIN` handles zero-variant products, gives one consistent snapshot, and
one round trip.

## Data Flow

```
                  ┌── products/application ── ProductRepository (port, async)
composition root ─┤
 (test / future   └── stock/application ───── StockMovementRepository (record only)
  admin route)                                StockLevelReader
        │
        │  async with transaction(pool) as conn:   ← BEGIN (shared/infrastructure)
        ▼
  RegisterStockedProductUseCase(products=…, movements=…)
        │
        ├─→ PostgresProductRepository(conn)  ──→ products, product_variants
        └─→ PostgresStockMovementRepository(conn) ──→ stock_movements
                                                        │
                                     read back ←── variant_stock_levels (view)
```

### Sequence: atomic register with initial stock

```
caller        transaction()      UseCase      ProductRepo   MovementRepo    Postgres
  │  acquire conn  │                │              │             │             │
  ├───────────────>│  BEGIN ────────┼──────────────┼─────────────┼────────────>│
  ├── execute ────────────────────> │              │             │             │
  │                │                ├─ add(product)┼────────────>│ INSERT products
  │                │                │              ├─ executemany──────────────>│ INSERT product_variants
  │                │                ├─ record(m) ──┼────────────>│ INSERT stock_movements
  │                │                │              │             │             │
  │  <── ok ───────┤  COMMIT ───────┴──────────────┴─────────────┴────────────>│
  │                │                                                           │
  │  raise ────────┤  ROLLBACK  (no products row, no variants, no movements)   │
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/src/gcell/shared/infrastructure/postgres.py` | Create | `create_pool`, `close_pool`, `transaction(pool_or_conn)`, `Executor` protocol |
| `backend/src/gcell/shared/infrastructure/config.py` | Create | `db_url()` from `os.environ` — no new dotenv dependency |
| `backend/src/gcell/main.py` | Modify | `lifespan` → `app.state.db_pool` |
| `backend/src/gcell/products/domain/product.py` | Modify | `id`/`slug`/`model`/`color`, `Decimal`, id-based equality |
| `backend/src/gcell/products/application/repository.py` | Modify | async `add`/`get_by_id`/`get_by_slug`/`list_all` |
| `backend/src/gcell/products/application/exceptions.py` | Create | `DuplicateProductSlugError` |
| `backend/src/gcell/products/application/register_product.py` | Modify | async; pre-check removed |
| `backend/src/gcell/products/infrastructure/postgres_product_repository.py` | Create | Connection-scoped adapter |
| `backend/src/gcell/products/infrastructure/in_memory_product_repository.py` | Modify | async, id-keyed + slug index, same exception |
| `backend/src/gcell/stock/domain/stock_movement.py` | Create | `MovementType`, frozen `StockMovement` |
| `backend/src/gcell/stock/application/{stock_movement_repository,stock_level_reader,record_stock_movement,register_stocked_product,exceptions}.py` | Create | Ports + 2 use cases + `UnknownVariantError` |
| `backend/src/gcell/stock/infrastructure/{postgres_stock_movement_repository,postgres_stock_level_reader}.py` | Create | Insert-only adapter + view reader |
| `backend/pyproject.toml` | Modify | `asyncpg` dep; `asyncio_default_fixture_loop_scope` |
| `backend/.env.example` | Create | `DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres` |
| `backend/tests/conftest.py` | Create | `db_pool`, `db_conn` (rollback-isolated) |
| `backend/tests/unit/products/*.py` | Modify | `Decimal` fixtures, new field names, async tests |
| `backend/tests/integration/db/*.py` | Create | Postgres round-trip, atomicity, ledger tests |
| `backend/tests/integration/api/test_health.py` | Modify | `with TestClient(app) as client:` |
| `backend/tests/architecture/test_domain_boundary.py` | Modify | `asyncpg` in `BANNED_MODULES`; new `application/` sweep |

## Interfaces / Contracts

```python
# products/domain/product.py
@dataclass(eq=False)
class ProductVariant:
    id: UUID
    color: str
    price: Decimal
    cost: Decimal
    # __post_init__: color non-blank; price/cost are Decimal instances (TypeError on
    # float — silent precision loss), is_finite() (numeric accepts NaN), >= 0,
    # exponent >= -2 (numeric(10,2) would round silently and break round-trip equality).
    # __eq__/__hash__ on id.

@dataclass(eq=False)
class Product:
    id: UUID
    slug: str
    name: str
    model: str
    variants: list[ProductVariant] = field(default_factory=list)
    # __post_init__: name/model non-blank; slug matches ^[a-z0-9]+(-[a-z0-9]+)*$
    # and len 1..80 — mirrors products_slug_format_check / _length_check.
    # ProductVariant carries no product_id: the adapter derives it from the root.

# products/application/repository.py
class ProductRepository(Protocol):
    async def add(self, product: Product) -> None: ...
    async def get_by_id(self, product_id: UUID) -> Product | None: ...
    async def get_by_slug(self, slug: str) -> Product | None: ...
    async def list_all(self) -> list[Product]: ...

# stock/domain/stock_movement.py
class MovementType(StrEnum):
    RESTOCK = "restock"; SALE = "sale"; RETURN = "return"
    BREAKAGE = "breakage"; ADJUSTMENT = "adjustment"

@dataclass(frozen=True)
class StockMovement:
    variant_id: UUID
    movement_type: MovementType
    quantity_delta: int
    reason: str | None = None
    # __post_init__ mirrors stock_movements_sign_direction_check exactly:
    # delta != 0; RESTOCK/RETURN > 0; SALE/BREAKAGE < 0; ADJUSTMENT either.
    # reason, when present, must not be blank (domain-only rule, no DB counterpart).

# stock/application — append-only is structural: one method, no update/delete.
class StockMovementRepository(Protocol):
    async def record(self, movement: StockMovement) -> None: ...

class StockLevelReader(Protocol):
    async def quantity_on_hand(self, variant_id: UUID) -> int: ...

# RecordStockMovementUseCase.execute takes primitives (variant_id, movement_type: str,
# quantity_delta, reason), resolves str -> MovementType (ValueError on unknown), builds
# the entity (which enforces sign rules), records it. Invalid input fails in the domain,
# never as a raw CheckViolationError.
```

### SQL

```sql
-- add(): both statements inside the caller's transaction
INSERT INTO products (id, slug, name, model) VALUES ($1, $2, $3, $4);
-- conn.executemany, one tuple per variant
INSERT INTO product_variants (id, product_id, color, price, cost) VALUES ($1,$2,$3,$4,$5);

-- get_by_slug / get_by_id / list_all (WHERE swapped or dropped)
SELECT p.id, p.slug, p.name, p.model,
       v.id AS variant_id, v.color, v.price, v.cost
FROM products p
LEFT JOIN product_variants v ON v.product_id = p.id
WHERE p.slug = $1
ORDER BY v.created_at, v.id;

INSERT INTO stock_movements (variant_id, movement_type, quantity_delta, reason)
VALUES ($1, $2, $3, $4);   -- id is DB-assigned identity; no RETURNING needed

SELECT coalesce(
  (SELECT quantity_on_hand FROM variant_stock_levels WHERE variant_id = $1), 0);
```

`products.description` is intentionally not written — it is nullable and not modeled by
`Product` in this change.

### Decimal round-trip

asyncpg maps `numeric` ↔ `decimal.Decimal` natively; **no cast, no `::numeric`, no
`set_type_codec` is required**. Two grounded consequences:
1. Passing a `float` to a `numeric` parameter raises at the driver, which is why the domain
   rejects non-`Decimal` money up front rather than relying on that error.
2. Postgres returns the column at scale 2 (`Decimal("45000.00")`). `Decimal.__eq__` compares
   numeric value, so `Decimal("45000") == Decimal("45000.00")` is `True` and hashes match —
   but `str()`/`repr()` differ, so assertions MUST compare values, never strings.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit (domain) | Every `__post_init__` invariant; id-based equality; sign-direction rules per `MovementType` | pytest, pure Python, no DB |
| Unit (application) | `RegisterProductUseCase`, `RecordStockMovementUseCase`, `RegisterStockedProductUseCase` | async in-memory adapters raising the same exception types |
| Integration (DB) | Round-trip by `slug`/`id` with `Decimal` intact; duplicate slug → `DuplicateProductSlugError`; unknown variant → `UnknownVariantError`; derived stock == movement sum; **atomicity: a failing variant/movement leaves zero `products` rows** | pytest-asyncio against local Postgres |
| Integration (API) | `/health` still 200 with the lifespan actually running | `with TestClient(app) as client:` |
| Architecture | `domain/` imports no `asyncpg`; `application/` imports no driver/framework; `transaction()` is the only `acquire()` call site | AST walk + source grep |

**Fixtures** (`backend/tests/conftest.py`):

```python
@pytest.fixture
async def db_pool():                       # function-scoped on purpose
    dsn = os.environ.get("DB_URL")
    if not dsn:
        pytest.skip("DB_URL not set — run `supabase start`")
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try: yield pool
    finally: await pool.close()

@pytest.fixture
async def db_conn(db_pool):                # per-test isolation, no truncation
    async with db_pool.acquire() as conn:
        tx = conn.transaction()
        await tx.start()
        try: yield conn
        finally: await tx.rollback()
```

Function-scoped pool avoids pytest-asyncio's session-loop/`loop_scope` friction at this
suite size; revisit if it gets slow. **This is why `transaction()` accepts a `Pool` *or* a
`Connection`**: tests hand it the already-in-transaction `db_conn`, asyncpg turns the nested
`conn.transaction()` into a SAVEPOINT, the code under test commits its savepoint, and the
outer rollback still erases everything. Tests are ordering-independent and leave no rows.

`test_health.py` keeps passing unchanged today because `TestClient` without `with` never
runs lifespan — which is exactly the problem. Switching to `with TestClient(app) as client:`
makes a broken lifespan fail the test instead of shipping green.

`BANNED_MODULES` gains `"asyncpg"`. `DOMAINS` already contains `"stock"`, so
`stock/domain/` is covered the moment the file exists — no list change. A second sweep over
each domain's `application/` banning `{asyncpg, fastapi, pydantic}` is recommended here
specifically because this change is where a port could accidentally accept an
`asyncpg.Connection`; the tasks phase may defer it if the slice gets too large.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or
process-integration boundary. `DB_URL` is ordinary configuration; `.env` stays gitignored
and `.env.example` carries the local Docker credential only.

## Migration / Rollout

No migration required. The schema is untouched; the DSN is a superuser connection that
bypasses RLS by design (authorization lands with the admin route layer). Rollback is a
plain revert — the in-memory adapter stays in the tree.

## Open Questions

- [ ] Extend the domain-boundary AST walk to `application/` in this change, or split it out?
- [ ] Should `Product` model `description` now, or wait for the admin form change?
- [ ] `StockLevelReader` bulk read (`dict[UUID, int]`) is deferred — the future admin list
      view will need it to avoid N+1.
