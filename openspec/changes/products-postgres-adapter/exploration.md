# Exploration: products-postgres-adapter

Wiring the FastAPI backend's `products` domain to the real Postgres database, as the deferred fast-follow from `supabase-schema`.

## Current State

`backend/src/gcell/products/` is a pure in-memory scaffold with zero DB dependency:
- `domain/product.py`: `@dataclass Product(name, variants)`, `@dataclass ProductVariant(phone_model, price: float, cost: float)`. No `id`, no `color`, no `slug`. Default dataclass value-equality (unhashable).
- `application/repository.py`: sync `ProductRepository` Protocol — `add`, `get_by_name(name)`, `list_all`.
- `infrastructure/in_memory_product_repository.py`: dict keyed by `product.name`.
- `application/register_product.py`: `RegisterProductUseCase` rejects duplicates via `get_by_name`.
- `backend/pyproject.toml`: only `fastapi` runtime dep; dev deps `httpx`, `pytest`, `pytest-asyncio` (`asyncio_mode=auto`), `ruff`. No DB client anywhere.
- `backend/tests/architecture/test_domain_boundary.py`: AST-walks only each domain's `domain/` folder, banning `{fastapi, pydantic, supabase, sqlalchemy, httpx}`. Does **not** include `asyncpg`/`psycopg` — a minor blind spot worth closing once a driver is picked.
- `backend/src/gcell/stock/{domain,application,infrastructure}/__init__.py` already exist as **empty stub folders** — a strong architectural signal that stock/inventory was intended as its own bounded context, separate from `products`.
- `main.py` has zero lifespan hooks; `test_health.py` builds `TestClient(app)` without a `with` context manager.
- No `.env`/`.env.example` under `backend/`. No CI (`.github/workflows` absent) — confirmed.

## Real Postgres Schema (ground truth)

- `products`: `id uuid PK`, `slug UNIQUE` (+ format/length CHECK), `name`, `model` (the phone model — **lives on product, not variant**), nullable `description`.
- `product_variants`: `id uuid PK`, `product_id FK`, `color`, `price numeric(10,2)`, `cost numeric(10,2)`, composite `UNIQUE(product_id, id)`.
- `product_images`: `id`, `product_id`, nullable `variant_id`, `storage_path`, `alt_text`, `sort_order`; composite FK with `MATCH SIMPLE`.
- `stock_movements`: append-only, `bigint identity PK`, `variant_id FK ... ON DELETE RESTRICT`, `movement_type` CHECK-enum, sign-direction CHECK, covering index. A `BEFORE UPDATE OR DELETE FOR EACH ROW` trigger unconditionally raises — fires for any role (not role-bypassed).
- `variant_stock_levels` (internal view): live `SUM(quantity_delta)` per variant — stock is always derived, never stored.
- RLS: `service_role` gets full CRUD on `products`/`product_variants`/`product_images`, but only `SELECT/INSERT` (no UPDATE/DELETE) on `stock_movements`. Public reads go through `catalog_*` views (out of scope, already working).
- Archived `supabase-schema` design doc (Decision #9) explicitly named `numeric(10,2)` vs domain `float` as a deliberate divergence and stated "the fast-follow should move Python to `Decimal`" — this change is that named target.

## Affected Areas

- `backend/src/gcell/products/domain/product.py` — add `id`/`slug`/`model`(moved from variant)/`color`; `float`->`Decimal`; identity-based equality.
- `backend/src/gcell/products/application/repository.py` — `get_by_name`->`get_by_slug`/`get_by_id`; likely new async signatures.
- `backend/src/gcell/products/infrastructure/` — new `PostgresProductRepository` adapter (only place a DB client import is allowed).
- `backend/src/gcell/products/application/register_product.py` — duplicate-check currently keys on `get_by_name`, but only `slug` is DB-unique (real bug once persisted).
- `backend/pyproject.toml` — add DB driver dependency.
- `backend/src/gcell/main.py` — needs a lifespan hook for pool startup/shutdown.
- `backend/tests/architecture/test_domain_boundary.py` — optionally extend `BANNED_MODULES` with the chosen driver.
- `backend/tests/integration/api/test_health.py` — may need `with TestClient(app) as client:` once DB startup exists.
- `backend/src/gcell/stock/` — currently empty; candidate home for `stock_movements` persistence instead of `products/`.

## Approaches

### 1. Minimal (recommended starting point)
Swap in-memory->Postgres for `list_all`/`get_by_slug`(+`get_by_id`)/basic `add` (product+variants); no stock ledger writes, no images.
- Pros: fits the 400-line review budget more easily; unblocks "create product" for a future admin UI; clean value-object reconciliation without touching the stock boundary question.
- Cons: doesn't yet deliver "adjust stock, record cost" — the user's stated motivation for this change — so may feel incomplete on its own.
- Effort: Medium

### 2. Medium
Minimal + `record_stock_movement` use case (append-only insert) + `quantity_on_hand` reads via `variant_stock_levels`.
- Pros: delivers the actual admin-write motivation.
- Cons: raises an unresolved cross-domain question — should ledger writes live in `products/` or in the already-scaffolded (empty) `stock/` domain? Doing it in `products/` risks having to redo it when `stock/` gets built out.
- Effort: High

### 3. Full
Medium + `product_images` CRUD + update/delete.
- Pros: complete CRUD story.
- Cons: `ON DELETE RESTRICT` from `product_variants`->`stock_movements` means delete is DB-blocked once any stock history exists — a genuinely harder, separate design problem, not just more of the same work.
- Effort: Very High, likely exceeds the review budget alone.

## DB Client Recommendation

**asyncpg (direct)** over `supabase-py`/PostgREST. `DB_URL` connects as the Postgres **superuser** (bypasses RLS by being superuser, not via the `service_role` JWT/PostgREST mechanism — these are genuinely different privilege paths). Direct asyncpg gives native `Decimal` for `numeric(10,2)` (no PostgREST JSON round-trip), real multi-statement transactions (needed for atomic variant+movement inserts, which PostgREST can't do without a Postgres RPC function), no extra HTTP hop, and clean FastAPI lifespan pool management. The append-only trigger still protects `stock_movements` regardless of connection strategy since triggers aren't role-bypassed.

## Testing Strategy

pytest-asyncio + real local Postgres (matches this project's established real-Supabase-not-mocks convention). Recommend per-test transaction rollback as the primary isolation strategy.

## Recommendation

Scope this change to **Option 1 (minimal)**, but have `sdd-propose` explicitly surface — rather than silently decide — whether stock-ledger writes belong in this change or in a sibling `stock` domain change. The pre-existing empty `stock/` scaffold strongly signals separation was intended, but the user's stated motivation (admin needs to adjust stock/record cost) suggests they may want at least a first vertical stock slice now. Also flag a real bug found in passing: `RegisterProductUseCase`'s duplicate-check must move from `get_by_name` to `get_by_slug` to match the actual DB uniqueness constraint.

## Risks

- Append-only `stock_movements` trigger makes naive "update stock" impossible by design; `ProductVariant` has zero stock concept today.
- `RegisterProductUseCase` duplicate-check uses `get_by_name`, but only `slug` is DB-unique.
- `float`->`Decimal` breaks existing test fixtures (`45000.0` literals) — not purely additive.
- `test_domain_boundary.py`'s `BANNED_MODULES` doesn't cover the eventual DB driver package (low risk, worth adding defensively).
- No `.env`/secret-loading convention exists yet for `DB_URL`/service-role credentials; must land in `infrastructure/` only.
- `main.py` has no lifespan hooks; adding mandatory DB startup could break `test_health.py` unless startup is lazy or the test adopts `with TestClient(...)`.
- `product_variants -> stock_movements` is `ON DELETE RESTRICT`: full delete is DB-blocked once stock history exists.

## Ready for Proposal

Yes — with one open decision to carry into `sdd-propose`: whether stock-ledger writes (Option 2) are in-scope now or deferred to a sibling `stock` domain change.
