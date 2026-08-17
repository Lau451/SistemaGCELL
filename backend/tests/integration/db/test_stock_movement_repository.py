"""Integration tests for `PostgresStockMovementRepository` and
`PostgresStockLevelReader` against real local Postgres.

Uses `db_conn` (per-test rollback isolation, see `tests/conftest.py`). Every
movement needs an existing `variant_id`, so each test first persists a
product+variant through `PostgresProductRepository` sharing the SAME
connection -- both adapters live inside the one rollback-isolated
transaction.
"""

from datetime import UTC, datetime, timedelta
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
from gcell.stock.infrastructure.postgres_stock_movement_history_reader import (
    PostgresStockMovementHistoryReader,
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


async def insert_movement_at(
    conn: asyncpg.Connection, variant_id, created_at: datetime, quantity_delta: int = 1
) -> None:
    """Direct SQL insert bypassing `PostgresStockMovementRepository.record`
    (which never accepts `created_at` -- it's DB-assigned via `default
    now()`). `created_at` is not touched by the append-only trigger, which
    only rejects `UPDATE`/`DELETE`, so an explicit `INSERT` value is fine
    and is the only way to control boundary timestamps deterministically in
    these tests.
    """
    await conn.execute(
        "INSERT INTO stock_movements (variant_id, movement_type, quantity_delta, "
        "reason, created_at) VALUES ($1, $2, $3, $4, $5)",
        variant_id,
        "adjustment",
        quantity_delta,
        None,
        created_at,
    )


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


async def test_quantities_for_variants_matches_each_variants_quantity_on_hand(
    db_conn,
) -> None:
    variant_a_id = await make_persisted_variant_id(db_conn)
    variant_b_id = await make_persisted_variant_id(db_conn)
    repository = PostgresStockMovementRepository(db_conn)
    reader = PostgresStockLevelReader(db_conn)
    await repository.record(
        StockMovement(
            variant_id=variant_a_id, movement_type=MovementType.RESTOCK, quantity_delta=10
        )
    )
    await repository.record(
        StockMovement(
            variant_id=variant_a_id, movement_type=MovementType.SALE, quantity_delta=-3
        )
    )
    await repository.record(
        StockMovement(
            variant_id=variant_b_id, movement_type=MovementType.RESTOCK, quantity_delta=20
        )
    )

    quantities = await reader.quantities_for_variants([variant_a_id, variant_b_id])

    assert quantities == {variant_a_id: 7, variant_b_id: 20}


async def test_quantities_for_variants_id_with_no_movements_resolves_to_zero(
    db_conn,
) -> None:
    variant_id = await make_persisted_variant_id(db_conn)
    reader = PostgresStockLevelReader(db_conn)

    quantities = await reader.quantities_for_variants([variant_id])

    assert quantities == {variant_id: 0}


async def test_quantities_for_variants_excludes_ids_not_requested(db_conn) -> None:
    requested_id = await make_persisted_variant_id(db_conn)
    other_id = await make_persisted_variant_id(db_conn)
    repository = PostgresStockMovementRepository(db_conn)
    reader = PostgresStockLevelReader(db_conn)
    await repository.record(
        StockMovement(
            variant_id=other_id, movement_type=MovementType.RESTOCK, quantity_delta=99
        )
    )

    quantities = await reader.quantities_for_variants([requested_id])

    assert quantities == {requested_id: 0}
    assert other_id not in quantities


async def test_quantities_for_variants_empty_input_returns_empty_dict(db_conn) -> None:
    reader = PostgresStockLevelReader(db_conn)

    assert await reader.quantities_for_variants([]) == {}


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


async def test_list_for_variant_returns_rows_newest_first(db_conn) -> None:
    variant_id = await make_persisted_variant_id(db_conn)
    repository = PostgresStockMovementRepository(db_conn)
    reader = PostgresStockMovementHistoryReader(db_conn)
    for delta in (10, -3, 2):
        await repository.record(
            StockMovement(
                variant_id=variant_id, movement_type=MovementType.ADJUSTMENT, quantity_delta=delta
            )
        )

    rows = await reader.list_for_variant(variant_id, limit=10, before_id=None)

    assert [row.quantity_delta for row in rows] == [2, -3, 10]
    assert rows[0].id > rows[1].id > rows[2].id


async def test_list_for_variant_paginates_with_strictly_exclusive_before_id_cursor(
    db_conn,
) -> None:
    variant_id = await make_persisted_variant_id(db_conn)
    repository = PostgresStockMovementRepository(db_conn)
    reader = PostgresStockMovementHistoryReader(db_conn)
    for _ in range(5):
        await repository.record(
            StockMovement(
                variant_id=variant_id, movement_type=MovementType.ADJUSTMENT, quantity_delta=1
            )
        )

    page_one = await reader.list_for_variant(variant_id, limit=2, before_id=None)
    page_two = await reader.list_for_variant(
        variant_id, limit=2, before_id=page_one[-1].id
    )

    page_one_ids = {row.id for row in page_one}
    page_two_ids = {row.id for row in page_two}
    assert len(page_one) == 2
    assert len(page_two) == 2
    assert page_one_ids.isdisjoint(page_two_ids)  # no duplicates
    assert max(page_two_ids) < min(page_one_ids)  # strictly older, no gaps skipped


async def test_list_for_variant_never_returns_another_variants_movements(db_conn) -> None:
    variant_a_id = await make_persisted_variant_id(db_conn)
    variant_b_id = await make_persisted_variant_id(db_conn)
    repository = PostgresStockMovementRepository(db_conn)
    reader = PostgresStockMovementHistoryReader(db_conn)
    await repository.record(
        StockMovement(
            variant_id=variant_a_id, movement_type=MovementType.RESTOCK, quantity_delta=10
        )
    )
    await repository.record(
        StockMovement(
            variant_id=variant_b_id, movement_type=MovementType.RESTOCK, quantity_delta=20
        )
    )

    rows = await reader.list_for_variant(variant_a_id, limit=10, before_id=None)

    assert len(rows) == 1
    assert rows[0].variant_id == variant_a_id


# ---------------------------------------------------------------------------
# since/until date filtering (design.md DD1, D10, D11) --
# admin-stock-movement-date-filter
# ---------------------------------------------------------------------------


async def test_list_for_variant_since_and_until_are_inclusive_of_boundary_rows(
    db_conn,
) -> None:
    variant_id = await make_persisted_variant_id(db_conn)
    reader = PostgresStockMovementHistoryReader(db_conn)
    since = datetime(2026, 1, 10, tzinfo=UTC)
    until = datetime(2026, 1, 20, tzinfo=UTC)
    await insert_movement_at(db_conn, variant_id, since)  # exactly at since -- included
    await insert_movement_at(db_conn, variant_id, until)  # exactly at until -- included
    await insert_movement_at(
        db_conn, variant_id, since - timedelta(seconds=1)
    )  # before since -- excluded
    await insert_movement_at(
        db_conn, variant_id, until + timedelta(seconds=1)
    )  # after until -- excluded

    rows = await reader.list_for_variant(
        variant_id, limit=10, before_id=None, since=since, until=until
    )

    assert {row.created_at for row in rows} == {since, until}


async def test_list_for_variant_range_and_before_id_predicate_compose_without_gaps(
    db_conn,
) -> None:
    variant_id = await make_persisted_variant_id(db_conn)
    reader = PostgresStockMovementHistoryReader(db_conn)
    base = datetime(2026, 1, 1, tzinfo=UTC)
    since = base
    until = base + timedelta(days=10)
    for day in range(5):
        await insert_movement_at(db_conn, variant_id, base + timedelta(days=day))
    await insert_movement_at(db_conn, variant_id, base + timedelta(days=20))  # out of range

    page_one = await reader.list_for_variant(
        variant_id, limit=2, before_id=None, since=since, until=until
    )
    page_two = await reader.list_for_variant(
        variant_id, limit=2, before_id=page_one[-1].id, since=since, until=until
    )
    page_three = await reader.list_for_variant(
        variant_id, limit=2, before_id=page_two[-1].id, since=since, until=until
    )

    all_rows = page_one + page_two + page_three
    all_ids = [row.id for row in all_rows]
    assert len(all_ids) == 5  # all 5 in-range rows seen, the out-of-range row never appears
    assert len(set(all_ids)) == 5  # no duplicates across pages
    assert all_ids == sorted(all_ids, reverse=True)  # no gaps skipped


async def test_list_for_variant_date_filter_is_scoped_to_the_requested_variant(
    db_conn,
) -> None:
    variant_a_id = await make_persisted_variant_id(db_conn)
    variant_b_id = await make_persisted_variant_id(db_conn)
    reader = PostgresStockMovementHistoryReader(db_conn)
    instant = datetime(2026, 1, 15, tzinfo=UTC)
    await insert_movement_at(db_conn, variant_a_id, instant)
    await insert_movement_at(db_conn, variant_b_id, instant)

    rows = await reader.list_for_variant(
        variant_a_id,
        limit=10,
        before_id=None,
        since=instant - timedelta(days=1),
        until=instant + timedelta(days=1),
    )

    assert len(rows) == 1
    assert rows[0].variant_id == variant_a_id
