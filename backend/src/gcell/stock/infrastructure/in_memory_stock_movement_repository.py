"""In-memory adapter for `StockMovementRepository`.

Mirrors `products/infrastructure/in_memory_product_repository.py`'s role:
lets the application layer be exercised end-to-end without Postgres wiring.
`recorded` is exposed as a plain list (not hidden behind an accessor) so
unit tests can assert both content AND the append-only ordering directly --
this adapter has no update/delete method either, matching the port shape.
"""

from gcell.stock.domain.stock_movement import StockMovement


class InMemoryStockMovementRepository:
    def __init__(self) -> None:
        self.recorded: list[StockMovement] = []

    async def record(self, movement: StockMovement) -> None:
        self.recorded.append(movement)
