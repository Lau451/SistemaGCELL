"""In-memory adapter for `StockLevelReader`.

Derives `quantity_on_hand` the same way the `variant_stock_levels` view
does -- `SUM(quantity_delta)` per `variant_id` -- from an in-memory list of
recorded movements, so it can be composed directly with
`InMemoryStockMovementRepository` in tests without any DB wiring.
"""

from uuid import UUID

from gcell.stock.domain.stock_movement import StockMovement


class InMemoryStockLevelReader:
    def __init__(self, movements: list[StockMovement]) -> None:
        self._movements = movements

    async def quantity_on_hand(self, variant_id: UUID) -> int:
        return sum(
            movement.quantity_delta
            for movement in self._movements
            if movement.variant_id == variant_id
        )
