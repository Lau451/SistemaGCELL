"""Unit tests for `RecordStockMovementUseCase` (+ its in-memory test double).

Still framework-free: only `gcell.stock.*` is imported. Proves the use case
resolves `movement_type: str -> MovementType` and rejects both an unknown
type and a wrong-sign quantity BEFORE any persistence is attempted -- see
spec's "Movement Type And Sign Are Validated In The Domain" requirement.
"""

from uuid import uuid4

import pytest

from gcell.stock.application.record_stock_movement import RecordStockMovementUseCase
from gcell.stock.domain.stock_movement import MovementType
from gcell.stock.infrastructure.in_memory_stock_movement_repository import (
    InMemoryStockMovementRepository,
)


async def test_valid_movement_is_recorded() -> None:
    repository = InMemoryStockMovementRepository()
    use_case = RecordStockMovementUseCase(repository=repository)
    variant_id = uuid4()

    result = await use_case.execute(
        variant_id=variant_id, movement_type="restock", quantity_delta=10
    )

    assert result.variant_id == variant_id
    assert result.movement_type == MovementType.RESTOCK
    assert result.quantity_delta == 10
    assert repository.recorded == [result]


async def test_unknown_movement_type_is_rejected_before_persistence() -> None:
    repository = InMemoryStockMovementRepository()
    use_case = RecordStockMovementUseCase(repository=repository)

    with pytest.raises(ValueError):
        await use_case.execute(
            variant_id=uuid4(), movement_type="theft", quantity_delta=5
        )

    assert repository.recorded == []


async def test_wrong_sign_quantity_for_type_is_rejected_before_persistence() -> None:
    repository = InMemoryStockMovementRepository()
    use_case = RecordStockMovementUseCase(repository=repository)

    with pytest.raises(ValueError):
        await use_case.execute(
            variant_id=uuid4(), movement_type="sale", quantity_delta=5
        )

    assert repository.recorded == []


async def test_reason_is_recorded_when_provided() -> None:
    repository = InMemoryStockMovementRepository()
    use_case = RecordStockMovementUseCase(repository=repository)

    result = await use_case.execute(
        variant_id=uuid4(),
        movement_type="breakage",
        quantity_delta=-1,
        reason="Dropped during unboxing",
    )

    assert result.reason == "Dropped during unboxing"
