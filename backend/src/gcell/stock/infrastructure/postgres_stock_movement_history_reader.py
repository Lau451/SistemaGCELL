"""Postgres adapter for `StockMovementHistoryReader`.

Takes an `asyncpg.Connection` (never a `Pool`) -- same pattern as
`PostgresStockMovementRepository` and `PostgresStockLevelReader`. A NEW
sibling adapter, not a method on `PostgresStockMovementRepository` (design.md
Decision 2): read and write adapters are already split for the same ledger
data, and adding a read method there would falsify that adapter's own
docstring ("`record` is its only method").

Keyset pagination on `id DESC`, `before_id` strictly exclusive
(`id < $2`) -- served by `stock_movements_variant_id_covering_idx`. `limit`
is passed through as-is; clamping and the `limit + 1` trim both live in
`ListVariantStockMovementsUseCase`, never here.
"""

from uuid import UUID

import asyncpg

from gcell.stock.application.stock_movement_history_reader import RecordedStockMovement
from gcell.stock.domain.stock_movement import MovementType

_SELECT_HISTORY = """
    SELECT id, variant_id, movement_type, quantity_delta, reason, created_at
    FROM stock_movements
    WHERE variant_id = $1 AND ($2::bigint IS NULL OR id < $2)
    ORDER BY id DESC
    LIMIT $3
"""


class PostgresStockMovementHistoryReader:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def list_for_variant(
        self, variant_id: UUID, limit: int, before_id: int | None
    ) -> list[RecordedStockMovement]:
        rows = await self._conn.fetch(_SELECT_HISTORY, variant_id, before_id, limit)
        return [
            RecordedStockMovement(
                id=row["id"],
                variant_id=row["variant_id"],
                movement_type=MovementType(row["movement_type"]),
                quantity_delta=row["quantity_delta"],
                reason=row["reason"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
