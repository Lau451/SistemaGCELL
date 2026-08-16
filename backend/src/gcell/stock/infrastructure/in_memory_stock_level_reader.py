"""In-memory adapter for `StockLevelReader` and `CatalogStockLevelsReader`.

Derives `quantity_on_hand` the same way the `variant_stock_levels` view
does -- `SUM(quantity_delta)` per `variant_id` -- from an in-memory list of
recorded movements, so it can be composed directly with
`InMemoryStockMovementRepository` in tests without any DB wiring.

`quantities_for_variants` implements the bulk `CatalogStockLevelsReader`
port in lockstep with the single-variant method above (design.md Decision
1): same adapter class, both Protocols. Totality lives here -- every
requested id is seeded with `0` before the single pass over `self._movements`
overlays summed deltas, so a variant with no movements is never a missing
key (design.md Decision 2).
"""

from collections.abc import Sequence
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

    async def quantities_for_variants(
        self, variant_ids: Sequence[UUID]
    ) -> dict[UUID, int]:
        quantities = {variant_id: 0 for variant_id in variant_ids}
        requested = set(quantities)
        for movement in self._movements:
            if movement.variant_id in requested:
                quantities[movement.variant_id] += movement.quantity_delta
        return quantities
