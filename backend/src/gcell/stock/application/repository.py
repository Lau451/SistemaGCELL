"""Repository port for the stock domain.

Defined in `application/` (not `domain/`) -- same rationale as
`products/application/repository.py`: it is a boundary contract the
application layer depends on and infrastructure adapters implement.

Exactly ONE method, `record`. No update, no delete, no id-taking overload --
the append-only ledger invariant is a port-SHAPE fact, not merely
unimplemented. Derived stock is read through the separate `StockLevelReader`
port (`stock_level_reader.py`), never through this one -- see design.md
"append-only is a port-shape fact".
"""

from typing import Protocol

from gcell.stock.domain.stock_movement import StockMovement


class StockMovementRepository(Protocol):
    async def record(self, movement: StockMovement) -> None: ...
