"""Read port for derived current stock.

Backed by the `variant_stock_levels` view (`SUM(quantity_delta)` per
variant). Deliberately separate from `StockMovementRepository` -- the
ledger is the write model, this view is a derived read model, and a bulk
read (`dict[UUID, int]`) is explicitly out of scope for this change (see
design.md "Open Questions" and `openspec/changes/products-postgres-adapter/
tasks.md` Notes item 3).
"""

from typing import Protocol
from uuid import UUID


class StockLevelReader(Protocol):
    async def quantity_on_hand(self, variant_id: UUID) -> int: ...
