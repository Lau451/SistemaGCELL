"""Use case: list a variant's stock movement history, scoped to a
`product_id`, with the same ownership (IDOR) guard as
`RecordVariantStockMovementUseCase` -- a `variant_id` that does not exist,
or that belongs to a different product, raises `VariantNotFoundError`
BEFORE any `history_reader` call, never a distinguishable outcome (spec:
admin-stock-management "Movement History Ownership Is Checked Before Any
Read").

`limit` is clamped here (`max(1, min(limit, 100))`, default 20), not via
FastAPI `Query(le=100)` validation -- design.md Decision 3 says clamp, not
reject. The reader is asked for `limit + 1` rows and the result trimmed to
`limit`, so `next_before_id` is `None` exactly when the true end of the
ledger was reached, rather than after a wasted extra round-trip on the next
click.
"""

from dataclasses import dataclass
from uuid import UUID

from gcell.products.application.exceptions import ProductNotFoundError, VariantNotFoundError
from gcell.products.application.repository import ProductRepository
from gcell.stock.application.stock_movement_history_reader import (
    RecordedStockMovement,
    StockMovementHistoryReader,
)

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


@dataclass(frozen=True)
class StockMovementPage:
    items: list[RecordedStockMovement]
    next_before_id: int | None


@dataclass
class ListVariantStockMovementsUseCase:
    products: ProductRepository
    history_reader: StockMovementHistoryReader

    async def execute(
        self,
        product_id: UUID,
        variant_id: UUID,
        limit: int = _DEFAULT_LIMIT,
        before_id: int | None = None,
    ) -> StockMovementPage:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        if not any(variant.id == variant_id for variant in product.variants):
            raise VariantNotFoundError(variant_id, product_id)  # never 403 (IDOR)

        effective_limit = max(1, min(limit, _MAX_LIMIT))
        rows = await self.history_reader.list_for_variant(
            variant_id, effective_limit + 1, before_id
        )

        if len(rows) > effective_limit:
            trimmed = rows[:effective_limit]
            return StockMovementPage(items=trimmed, next_before_id=trimmed[-1].id)
        return StockMovementPage(items=rows, next_before_id=None)
