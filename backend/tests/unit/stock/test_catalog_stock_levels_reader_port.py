"""Port-shape proof for `CatalogStockLevelsReader`, plus behavior coverage
for the `InMemoryStockLevelReader.quantities_for_variants` implementation.

`CatalogStockLevelsReader` is a NEW sibling Protocol, deliberately NOT added
to `StockLevelReader` -- `test_stock_level_reader_port.py` asserts that
Protocol's public members are exactly `{"quantity_on_hand"}`, and widening it
would break that green test (design.md Decision 1).
"""

from uuid import uuid4

from gcell.stock.application.catalog_stock_levels_reader import (
    CatalogStockLevelsReader,
)
from gcell.stock.domain.stock_movement import MovementType, StockMovement
from gcell.stock.infrastructure.in_memory_stock_level_reader import (
    InMemoryStockLevelReader,
)


def test_catalog_stock_levels_reader_port_declares_exactly_one_method() -> None:
    public_members = {
        name for name in vars(CatalogStockLevelsReader) if not name.startswith("_")
    }

    assert public_members == {"quantities_for_variants"}


async def test_in_memory_quantities_for_variants_empty_input_returns_empty_dict() -> None:
    reader = InMemoryStockLevelReader([])

    result = await reader.quantities_for_variants([])

    assert result == {}


async def test_in_memory_quantities_for_variants_id_with_no_movements_resolves_to_zero() -> None:
    variant_id = uuid4()
    reader = InMemoryStockLevelReader([])

    result = await reader.quantities_for_variants([variant_id])

    assert result == {variant_id: 0}


async def test_in_memory_quantities_for_variants_id_with_movements_sums_deltas() -> None:
    variant_id = uuid4()
    movements = [
        StockMovement(
            variant_id=variant_id, movement_type=MovementType.RESTOCK, quantity_delta=10
        ),
        StockMovement(
            variant_id=variant_id, movement_type=MovementType.SALE, quantity_delta=-3
        ),
    ]
    reader = InMemoryStockLevelReader(movements)

    result = await reader.quantities_for_variants([variant_id])

    assert result == {variant_id: 7}


async def test_in_memory_quantities_for_variants_excludes_movements_of_unrequested_ids() -> None:
    requested_id = uuid4()
    other_id = uuid4()
    movements = [
        StockMovement(
            variant_id=requested_id, movement_type=MovementType.RESTOCK, quantity_delta=5
        ),
        StockMovement(
            variant_id=other_id, movement_type=MovementType.RESTOCK, quantity_delta=99
        ),
    ]
    reader = InMemoryStockLevelReader(movements)

    result = await reader.quantities_for_variants([requested_id])

    assert result == {requested_id: 5}
