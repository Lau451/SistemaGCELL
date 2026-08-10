"""Postgres adapter for `StockMovementRepository`.

Takes an `asyncpg.Connection` (never a `Pool`) -- same pattern as
`PostgresProductRepository`, so the caller always controls the transaction
boundary via `shared.infrastructure.postgres.transaction()`.

`stock_movements.id` is a DB-assigned `bigint generated always as identity`
-- no `RETURNING` needed, since `StockMovement` carries no id at all
(unlike `Product`/`ProductVariant`, which need a complete client-generated
id before insert for their id-based equality). The table is append-only at
the schema level (a `BEFORE UPDATE OR DELETE` trigger unconditionally
rejects mutation, see
`supabase/migrations/20260810000453_stock_movements_ledger.sql`); this
adapter never attempts one -- `record` is its only method, mirroring the
`StockMovementRepository` port shape.

The `INSERT` runs inside the shared `transaction()` helper -- same reason as
`PostgresProductRepository.add()`: a failed statement aborts the whole
enclosing Postgres transaction, so wrapping it as a nested SAVEPOINT means
only this single insert rolls back on a constraint violation, leaving a
caller's already-open transaction (e.g. a test's `db_conn`, or the
cross-domain `RegisterStockedProductUseCase` composition root) free to keep
running its own statements afterward -- including, when the caller does not
catch the translated exception, its own rollback of everything else.
"""

import asyncpg

from gcell.shared.infrastructure.postgres import transaction
from gcell.stock.application.exceptions import UnknownVariantError
from gcell.stock.domain.stock_movement import StockMovement

_INSERT_MOVEMENT = """
    INSERT INTO stock_movements (variant_id, movement_type, quantity_delta, reason)
    VALUES ($1, $2, $3, $4)
"""


class PostgresStockMovementRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def record(self, movement: StockMovement) -> None:
        try:
            async with transaction(self._conn) as conn:
                await conn.execute(
                    _INSERT_MOVEMENT,
                    movement.variant_id,
                    str(movement.movement_type),
                    movement.quantity_delta,
                    movement.reason,
                )
        except asyncpg.ForeignKeyViolationError as exc:
            if exc.constraint_name == "stock_movements_variant_id_fkey":
                raise UnknownVariantError(movement.variant_id) from exc
            raise
