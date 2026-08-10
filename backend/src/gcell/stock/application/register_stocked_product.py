"""Use case: atomically register a product (with variants) and its optional
initial stock movements.

Lives in `stock/application/` -- the legal dependency direction is
`stock -> products`, never the reverse (see `test_domain_boundary.py`'s
`DOMAINS` list and design.md's Data Flow section). This use case only
ORCHESTRATES the two ports; it owns no transaction. The composition root
(a future admin route, or an integration test) is responsible for handing
both `ProductRepository` and `StockMovementRepository` adapters that share
the SAME connection inside a `shared.infrastructure.postgres.transaction()`
scope -- otherwise atomicity does not hold. See design.md "transaction
boundary at the composition root, orchestration in a use case".

`initial_movements` defaults to an empty sequence: zero-stock product
registration MUST remain valid (spec's "Create with variants and no stock"
scenario) -- an initial movement is never required.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from gcell.products.application.repository import ProductRepository
from gcell.products.domain.product import Product
from gcell.stock.application.repository import StockMovementRepository
from gcell.stock.domain.stock_movement import StockMovement


@dataclass
class RegisterStockedProductUseCase:
    products: ProductRepository
    movements: StockMovementRepository

    async def execute(
        self,
        product: Product,
        initial_movements: Sequence[StockMovement] = (),
    ) -> Product:
        await self.products.add(product)
        for movement in initial_movements:
            await self.movements.record(movement)
        return product
