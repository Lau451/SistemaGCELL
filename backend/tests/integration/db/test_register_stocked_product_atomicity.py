"""Integration tests proving `RegisterStockedProductUseCase` is atomic
across BOTH the products domain (`products`/`product_variants`) AND the
stock domain (`stock_movements`) -- spec's "Product-With-Variants Insert Is
Atomic" requirement, extended to the cross-domain use case.

`stock_movements` is append-only at the schema level: its trigger rejects
UPDATE *and* DELETE unconditionally (even for a superuser connection), and
`stock_movements.variant_id` has `ON DELETE RESTRICT` on `product_variants`,
so a variant with even one committed movement can never be deleted either.
A genuinely-committed movement row is therefore PERMANENT -- there is no
valid cleanup statement. This dictates the two tests' harnesses below:

- The success path uses `db_conn` (per-test rollback isolation) so
  `transaction(db_conn)` becomes a nested SAVEPOINT -- rows are visible
  within the test via the SAME connection, and `db_conn`'s fixture teardown
  is a plain ROLLBACK (transaction control, not a DML UPDATE/DELETE), so the
  append-only trigger never fires and zero rows survive. This still proves
  `RegisterStockedProductUseCase` commits correctly across BOTH domains
  through the shared-connection pattern; the `transaction()` helper's
  real-Pool BEGIN/COMMIT mechanics are already proven generically by
  `test_postgres_transaction.py::test_transaction_with_pool_commits_on_clean_exit`.
- The failure path uses `db_pool` directly to exercise a REAL top-level
  `transaction(pool)` BEGIN/ROLLBACK -- safe to do because a ROLLED-BACK
  transaction commits nothing, so there is nothing to clean up:

    async with transaction(pool) as conn:
        await RegisterStockedProductUseCase(
            products=PostgresProductRepository(conn),
            movements=PostgresStockMovementRepository(conn),
        ).execute(product, initial_movements)

Both adapters are constructed with the SAME connection so they share one
transaction -- constructing them from two different `pool.acquire()` calls
would silently break atomicity, which is exactly the failure mode this
pattern (and the failure-path test) guards against.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)
from gcell.shared.infrastructure.postgres import transaction
from gcell.stock.application.exceptions import UnknownVariantError
from gcell.stock.application.register_stocked_product import (
    RegisterStockedProductUseCase,
)
from gcell.stock.domain.stock_movement import MovementType, StockMovement
from gcell.stock.infrastructure.postgres_stock_movement_repository import (
    PostgresStockMovementRepository,
)


def make_product(**overrides: object) -> Product:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "slug": f"funda-atomic-{uuid4().hex[:8]}",
        "name": "Funda atómica",
        "model": "iPhone 13",
        "variants": [
            ProductVariant(
                id=uuid4(),
                color="Negro",
                price=Decimal("45000.00"),
                cost=Decimal("30000.00"),
            )
        ],
    }
    defaults.update(overrides)
    return Product(**defaults)  # type: ignore[arg-type]


async def test_successful_registration_commits_product_variant_and_movement(
    db_conn,
) -> None:
    product = make_product()
    variant_id = product.variants[0].id
    initial_movement = StockMovement(
        variant_id=variant_id, movement_type=MovementType.RESTOCK, quantity_delta=20
    )

    async with transaction(db_conn) as conn:
        await RegisterStockedProductUseCase(
            products=PostgresProductRepository(conn),
            movements=PostgresStockMovementRepository(conn),
        ).execute(product, initial_movements=[initial_movement])

    product_row = await db_conn.fetchrow(
        "SELECT id FROM products WHERE id = $1", product.id
    )
    variant_row = await db_conn.fetchrow(
        "SELECT id FROM product_variants WHERE id = $1", variant_id
    )
    movement_row = await db_conn.fetchrow(
        "SELECT quantity_delta FROM stock_movements WHERE variant_id = $1",
        variant_id,
    )
    assert product_row is not None
    assert variant_row is not None
    assert movement_row is not None
    assert movement_row["quantity_delta"] == 20


async def test_failed_second_movement_leaves_zero_rows_in_both_domains(
    db_pool,
) -> None:
    """The second `initial_movement` targets a variant that does not exist,
    forcing a mid-transaction failure AFTER the product+variant insert
    already succeeded. The whole transaction must roll back: neither the
    product row, the variant row, nor ANY movement row (including the first,
    otherwise-valid one) may survive.
    """
    product = make_product()
    valid_variant_id = product.variants[0].id
    unknown_variant_id = uuid4()
    initial_movements = [
        StockMovement(
            variant_id=valid_variant_id,
            movement_type=MovementType.RESTOCK,
            quantity_delta=5,
        ),
        StockMovement(
            variant_id=unknown_variant_id,
            movement_type=MovementType.RESTOCK,
            quantity_delta=3,
        ),
    ]

    with pytest.raises(UnknownVariantError):
        async with transaction(db_pool) as conn:
            await RegisterStockedProductUseCase(
                products=PostgresProductRepository(conn),
                movements=PostgresStockMovementRepository(conn),
            ).execute(product, initial_movements=initial_movements)

    async with db_pool.acquire() as verify_conn:
        product_count = await verify_conn.fetchval(
            "SELECT count(*) FROM products WHERE id = $1", product.id
        )
        variant_count = await verify_conn.fetchval(
            "SELECT count(*) FROM product_variants WHERE product_id = $1", product.id
        )
        movement_count = await verify_conn.fetchval(
            "SELECT count(*) FROM stock_movements WHERE variant_id = $1",
            valid_variant_id,
        )
    assert product_count == 0
    assert variant_count == 0
    assert movement_count == 0
