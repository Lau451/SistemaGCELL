"""Integration tests for `PostgresStockMovementRepository` and
`PostgresStockLevelReader` against real local Postgres.

Uses `db_conn` (per-test rollback isolation, see `tests/conftest.py`). Every
movement needs an existing `variant_id`, so each test first persists a
product+variant through `PostgresProductRepository` sharing the SAME
connection -- both adapters live inside the one rollback-isolated
transaction.
"""

from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest

from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)
from gcell.stock.application.exceptions import UnknownVariantError
from gcell.stock.domain.stock_movement import MovementType, StockMovement
from gcell.stock.infrastructure.postgres_stock_level_reader import (
    PostgresStockLevelReader,
)
from gcell.stock.infrastructure.postgres_stock_movement_repository import (
    PostgresStockMovementRepository,
)


async def make_persisted_variant_id(conn: asyncpg.Connection) -> object:
    product = Product(
        id=uuid4(),
        slug=f"funda-stock-test-{uuid4().hex[:8]}",
        name="Funda de prueba",
        model="iPhone 13",
        variants=[
            ProductVariant(
                id=uuid4(),
                color="Negro",
                price=Decimal("45000.00"),
                cost=Decimal("30000.00"),
            )
        ],
    )
    await PostgresProductRepository(conn).add(product)
    return product.variants[0].id


async def test_record_persists_a_movement_row(db_conn) -> None:
    variant_id = await make_persisted_variant_id(db_conn)
    repository = PostgresStockMovementRepository(db_conn)
    movement = StockMovement(
        variant_id=variant_id,
        movement_type=MovementType.RESTOCK,
        quantity_delta=10,
        reason="Initial stock",
    )

    await repository.record(movement)

    row = await db_conn.fetchrow(
        "SELECT variant_id, movement_type, quantity_delta, reason "
        "FROM stock_movements WHERE variant_id = $1",
        variant_id,
    )
    assert row is not None
    assert row["variant_id"] == variant_id
    assert row["movement_type"] == "restock"
    assert row["quantity_delta"] == 10
    assert row["reason"] == "Initial stock"


async def test_ledger_sum_matches_recorded_movements_via_level_reader(db_conn) -> None:
    variant_id = await make_persisted_variant_id(db_conn)
    repository = PostgresStockMovementRepository(db_conn)
    reader = PostgresStockLevelReader(db_conn)
    await repository.record(
        StockMovement(
            variant_id=variant_id, movement_type=MovementType.RESTOCK, quantity_delta=10
        )
    )
    await repository.record(
        StockMovement(
            variant_id=variant_id, movement_type=MovementType.SALE, quantity_delta=-3
        )
    )

    quantity = await reader.quantity_on_hand(variant_id)

    assert quantity == 7


async def test_level_reader_returns_zero_for_variant_with_no_movements(db_conn) -> None:
    variant_id = await make_persisted_variant_id(db_conn)
    reader = PostgresStockLevelReader(db_conn)

    assert await reader.quantity_on_hand(variant_id) == 0


async def test_record_against_unknown_variant_raises_unknown_variant_error(
    db_conn,
) -> None:
    repository = PostgresStockMovementRepository(db_conn)
    unknown_variant_id = uuid4()
    movement = StockMovement(
        variant_id=unknown_variant_id,
        movement_type=MovementType.RESTOCK,
        quantity_delta=5,
    )

    with pytest.raises(UnknownVariantError) as exc_info:
        await repository.record(movement)

    assert exc_info.value.variant_id == unknown_variant_id
    row_count = await db_conn.fetchval(
        "SELECT count(*) FROM stock_movements WHERE variant_id = $1",
        unknown_variant_id,
    )
    assert row_count == 0


async def test_direct_update_against_stock_movements_is_rejected_by_trigger(
    db_conn,
) -> None:
    """`stock_movements` is append-only at the schema level (the
    `stock_movements_reject_mutation` trigger) -- proves this adapter's own
    lack of an update/delete method is backed by an unconditional DB
    guarantee, independent of any adapter restraint.
    """
    variant_id = await make_persisted_variant_id(db_conn)
    repository = PostgresStockMovementRepository(db_conn)
    await repository.record(
        StockMovement(
            variant_id=variant_id, movement_type=MovementType.RESTOCK, quantity_delta=10
        )
    )

    with pytest.raises(asyncpg.PostgresError, match="append-only"):
        await db_conn.execute(
            "UPDATE stock_movements SET quantity_delta = 99 WHERE variant_id = $1",
            variant_id,
        )
