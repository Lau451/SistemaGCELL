"""Read port for a variant's stock movement history.

Deliberately separate from the write-only `StockMovementRepository` (see
`stock/application/repository.py`'s single `record` method) -- read and
write adapters are already split for the same ledger data the same way
`StockLevelReader` is split from it (design.md Decision 2). Adding a read
method there would falsify `PostgresStockMovementRepository`'s docstring
("`record` is its only method") and its per-write `transaction()`
rationale.

`RecordedStockMovement` is a NEW application-layer read model, not an
extension of the domain `StockMovement` value object (design.md Decision
1): `StockMovement` is intentionally id-less and date-less (a ledger row's
id is DB-assigned, so value equality is correct there -- see
`stock/domain/stock_movement.py`), but a history view needs both `id` (the
keyset cursor) and `created_at` (a required date column). Adding either
field to `StockMovement` would break its documented equality rationale and
force `None` at every write site. This DTO reuses the domain `MovementType`
enum, and is colocated here because this port is its only consumer.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from gcell.stock.domain.stock_movement import MovementType


@dataclass(frozen=True)
class RecordedStockMovement:
    id: int
    variant_id: UUID
    movement_type: MovementType
    quantity_delta: int
    reason: str | None
    created_at: datetime


class StockMovementHistoryReader(Protocol):
    async def list_for_variant(
        self, variant_id: UUID, limit: int, before_id: int | None
    ) -> list[RecordedStockMovement]: ...
