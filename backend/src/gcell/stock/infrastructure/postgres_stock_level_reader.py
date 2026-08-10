"""Postgres adapter for `StockLevelReader`.

Reads the `variant_stock_levels` view (a live `SUM(quantity_delta)` grouped
by `variant_id`, see `supabase/migrations/20260810000458_public_catalog_rls.sql`).
A variant with zero recorded movements has no row in that view at all
(`GROUP BY` produces no empty-group row), so the query wraps it in
`coalesce(..., 0)` -- see design.md's SQL section.
"""

from uuid import UUID

import asyncpg

_SELECT_QUANTITY_ON_HAND = """
    SELECT coalesce(
        (SELECT quantity_on_hand FROM variant_stock_levels WHERE variant_id = $1), 0
    )
"""


class PostgresStockLevelReader:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def quantity_on_hand(self, variant_id: UUID) -> int:
        return await self._conn.fetchval(_SELECT_QUANTITY_ON_HAND, variant_id)
