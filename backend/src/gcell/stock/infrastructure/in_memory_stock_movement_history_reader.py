"""In-memory test double for `StockMovementHistoryReader`.

Mirrors `in_memory_stock_level_reader.py`'s role: composes directly with a
plain list of `RecordedStockMovement` rows so `ListVariantStockMovementsUseCase`
can be exercised end-to-end without Postgres wiring. Keyset semantics
(`id DESC`, exclusive `before_id`, `limit` applied as-is -- clamping is the
use case's job, not this adapter's) mirror
`PostgresStockMovementHistoryReader.list_for_variant` exactly, so unit tests
against this double stay representative of the real adapter's contract.
"""

from datetime import datetime
from uuid import UUID

from gcell.stock.application.stock_movement_history_reader import RecordedStockMovement


class InMemoryStockMovementHistoryReader:
    def __init__(self, movements: list[RecordedStockMovement]) -> None:
        self._movements = movements

    async def list_for_variant(
        self,
        variant_id: UUID,
        limit: int,
        before_id: int | None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> list[RecordedStockMovement]:
        rows = [m for m in self._movements if m.variant_id == variant_id]
        if before_id is not None:
            rows = [m for m in rows if m.id < before_id]
        if since is not None:
            rows = [m for m in rows if m.created_at >= since]
        if until is not None:
            rows = [m for m in rows if m.created_at <= until]
        rows.sort(key=lambda m: m.id, reverse=True)
        return rows[:limit]
