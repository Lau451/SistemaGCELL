"""Pure-domain unit tests for the stock domain.

No FastAPI, no Pydantic, no DB client is imported anywhere in this file or
in the module under test -- this test IS the hexagonal-boundary proof for
the stock domain. `StockMovement.__post_init__` must mirror
`stock_movements_sign_direction_check` from
`supabase/migrations/20260810000453_stock_movements_ledger.sql` exactly, so
an invalid movement never reaches the database.
"""

from dataclasses import FrozenInstanceError
from uuid import uuid4

import pytest

from gcell.stock.domain.stock_movement import MovementType, StockMovement


def make_movement(**overrides: object) -> StockMovement:
    defaults: dict[str, object] = {
        "variant_id": uuid4(),
        "movement_type": MovementType.RESTOCK,
        "quantity_delta": 10,
        "reason": None,
    }
    defaults.update(overrides)
    return StockMovement(**defaults)  # type: ignore[arg-type]


def test_restock_with_positive_quantity_is_accepted() -> None:
    movement = make_movement(movement_type=MovementType.RESTOCK, quantity_delta=10)

    assert movement.quantity_delta == 10


def test_restock_with_negative_quantity_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_movement(movement_type=MovementType.RESTOCK, quantity_delta=-1)


def test_return_with_positive_quantity_is_accepted() -> None:
    movement = make_movement(movement_type=MovementType.RETURN, quantity_delta=4)

    assert movement.quantity_delta == 4


def test_return_with_negative_quantity_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_movement(movement_type=MovementType.RETURN, quantity_delta=-4)


def test_sale_with_negative_quantity_is_accepted() -> None:
    movement = make_movement(movement_type=MovementType.SALE, quantity_delta=-2)

    assert movement.quantity_delta == -2


def test_sale_with_positive_quantity_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_movement(movement_type=MovementType.SALE, quantity_delta=5)


def test_breakage_with_negative_quantity_is_accepted() -> None:
    movement = make_movement(movement_type=MovementType.BREAKAGE, quantity_delta=-1)

    assert movement.quantity_delta == -1


def test_breakage_with_positive_quantity_is_rejected() -> None:
    with pytest.raises(ValueError):
        make_movement(movement_type=MovementType.BREAKAGE, quantity_delta=3)


def test_adjustment_allows_positive_quantity() -> None:
    movement = make_movement(movement_type=MovementType.ADJUSTMENT, quantity_delta=7)

    assert movement.quantity_delta == 7


def test_adjustment_allows_negative_quantity() -> None:
    movement = make_movement(movement_type=MovementType.ADJUSTMENT, quantity_delta=-7)

    assert movement.quantity_delta == -7


def test_quantity_delta_cannot_be_zero() -> None:
    with pytest.raises(ValueError):
        make_movement(movement_type=MovementType.ADJUSTMENT, quantity_delta=0)


def test_reason_defaults_to_none() -> None:
    movement = make_movement(reason=None)

    assert movement.reason is None


def test_reason_cannot_be_blank_when_provided() -> None:
    with pytest.raises(ValueError):
        make_movement(reason="   ")


def test_reason_can_be_a_non_blank_string() -> None:
    movement = make_movement(reason="Damaged in transit")

    assert movement.reason == "Damaged in transit"


def test_movement_is_immutable() -> None:
    movement = make_movement()

    with pytest.raises(FrozenInstanceError):
        movement.quantity_delta = 99  # type: ignore[misc]


def test_movement_equality_is_value_based() -> None:
    variant_id = uuid4()
    first = StockMovement(
        variant_id=variant_id,
        movement_type=MovementType.RESTOCK,
        quantity_delta=10,
        reason=None,
    )
    second = StockMovement(
        variant_id=variant_id,
        movement_type=MovementType.RESTOCK,
        quantity_delta=10,
        reason=None,
    )

    assert first == second
    assert hash(first) == hash(second)
