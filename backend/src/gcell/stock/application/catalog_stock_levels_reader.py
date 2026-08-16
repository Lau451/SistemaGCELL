"""Read port for bulk, catalog-wide current stock.

Sibling to `StockLevelReader`, deliberately NOT merged into it --
`tests/unit/stock/test_stock_level_reader_port.py` asserts that Protocol's
public members are exactly `{"quantity_on_hand"}`, and widening it would
break that green test (design.md Decision 1). This port answers a different
question -- "current stock for every variant in one call" -- backed by a
single aggregate query rather than one query per variant.

Totality contract: the returned dict MUST contain exactly one entry per
requested id, never a missing key. A variant with no recorded movements
resolves to `0` (design.md Decision 2) -- callers must never `.get(id, 0)`
to paper over an adapter that skips zero-movement variants.
"""

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID


class CatalogStockLevelsReader(Protocol):
    async def quantities_for_variants(
        self, variant_ids: Sequence[UUID]
    ) -> dict[UUID, int]: ...
