"""Use case: record a stock movement scoped to a `product_id`, with an
ownership (IDOR) guard.

`RecordStockMovementUseCase` has no concept of `product_id` at all, and
`admin.py`'s module docstring forbids a write route from calling
`PostgresProductRepository` directly -- the guard therefore needs one thin
composition use case here, in `stock/application/` (the `stock -> products`
dependency direction is already legal and exercised by
`RegisterStockedProductUseCase`). It adds no new port, no new domain
concept, and leaves every other `stock/` module byte-identical (design.md
Decision 1).

The scan runs against the already-fetched `product.variants` aggregate,
never a SQL join -- identical shape to
`UploadProductImageUseCase.execute`'s ownership check. `get_by_id`'s
`LEFT JOIN ... AND v.deleted_at IS NULL` means a soft-deleted variant is
already absent from `product.variants`, so the read-time soft-delete
cascade is inherited for free, with no extra query (see spec
"Movement Ownership Is Checked Before Any Write").
"""

from dataclasses import dataclass
from uuid import UUID

from gcell.products.application.exceptions import ProductNotFoundError, VariantNotFoundError
from gcell.products.application.repository import ProductRepository
from gcell.stock.application.record_stock_movement import RecordStockMovementUseCase
from gcell.stock.domain.stock_movement import StockMovement


@dataclass
class RecordVariantStockMovementUseCase:
    products: ProductRepository
    record_movement: RecordStockMovementUseCase

    async def execute(
        self,
        product_id: UUID,
        variant_id: UUID,
        movement_type: str,
        quantity_delta: int,
        reason: str | None = None,
    ) -> StockMovement:
        product = await self.products.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        if not any(variant.id == variant_id for variant in product.variants):
            raise VariantNotFoundError(variant_id, product_id)  # never 403 (IDOR)
        return await self.record_movement.execute(
            variant_id=variant_id,
            movement_type=movement_type,
            quantity_delta=quantity_delta,
            reason=reason,
        )
