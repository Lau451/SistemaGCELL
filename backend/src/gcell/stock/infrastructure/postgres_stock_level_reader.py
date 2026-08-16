"""Postgres adapter for `StockLevelReader` and `CatalogStockLevelsReader`.

Reads the `variant_stock_levels` view (a live `SUM(quantity_delta)` grouped
by `variant_id`, see `supabase/migrations/20260810000458_public_catalog_rls.sql`).
A variant with zero recorded movements has no row in that view at all
(`GROUP BY` produces no empty-group row), so `quantity_on_hand` wraps it in
`coalesce(..., 0)` -- see design.md's SQL section.

`quantities_for_variants` implements the bulk `CatalogStockLevelsReader`
port on this SAME adapter class (design.md Decision 1 -- the precedent of
splitting write/read adapters does not apply here, since this class is
already the read adapter for this exact view). One `ANY($1::uuid[])` query
regardless of variant count (design.md Decision 3); totality is handled in
Python, not SQL -- every requested id is seeded with `0` before the fetched
rows are overlaid, so a variant absent from the view (zero movements) is
never a missing key (design.md Decision 2).
"""

from collections.abc import Sequence
from uuid import UUID

import asyncpg

_SELECT_QUANTITY_ON_HAND = """
    SELECT coalesce(
        (SELECT quantity_on_hand FROM variant_stock_levels WHERE variant_id = $1), 0
    )
"""

_SELECT_QUANTITIES_FOR_VARIANTS = """
    SELECT variant_id, quantity_on_hand
    FROM variant_stock_levels
    WHERE variant_id = ANY($1::uuid[])
"""


class PostgresStockLevelReader:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def quantity_on_hand(self, variant_id: UUID) -> int:
        return await self._conn.fetchval(_SELECT_QUANTITY_ON_HAND, variant_id)

    async def quantities_for_variants(
        self, variant_ids: Sequence[UUID]
    ) -> dict[UUID, int]:
        if not variant_ids:
            return {}
        quantities = {variant_id: 0 for variant_id in variant_ids}
        rows = await self._conn.fetch(_SELECT_QUANTITIES_FOR_VARIANTS, list(variant_ids))
        for row in rows:
            quantities[row["variant_id"]] = row["quantity_on_hand"]
        return quantities
