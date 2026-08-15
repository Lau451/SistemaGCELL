"""Use case: create a new product with a server-derived slug AND optional
initial stock movements, atomically.

Lives in `stock/application/` -- the legal dependency direction is
`stock -> products`, never the reverse (see `register_stocked_product.py`'s
module docstring and `test_domain_boundary.py`'s `DOMAINS` list). Mirrors
`CreateProductUseCase` exactly (derive slug -> build `Product`), but
delegates persistence to `RegisterStockedProductUseCase` instead of
`RegisterProductUseCase` so the product, its variants, and any seed
movements are all recorded through the same atomic composition. See
design.md Decisions 1-2.

`initial_quantities` is a `{variant_id: quantity}` mapping rather than a
positional list -- avoids fragile index alignment with `variants`. Only
entries with `quantity > 0` become a `restock` `StockMovement`; `0`/absent
quantities never construct one. `StockMovement.__post_init__`'s non-zero
`quantity_delta` invariant stays a backstop only, never the mechanism (spec
"the domain's existing non-zero quantity_delta invariant...MUST be relied
upon, never bypassed").
"""

from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

from gcell.products.application.repository import ProductRepository
from gcell.products.application.slug import generate_unique_slug
from gcell.products.domain.product import Product, ProductVariant
from gcell.stock.application.register_stocked_product import (
    RegisterStockedProductUseCase,
)
from gcell.stock.application.repository import StockMovementRepository
from gcell.stock.domain.stock_movement import MovementType, StockMovement


@dataclass
class CreateStockedProductUseCase:
    products: ProductRepository
    movements: StockMovementRepository

    async def execute(
        self,
        name: str,
        model: str,
        variants: list[ProductVariant],
        initial_quantities: Mapping[UUID, int] | None = None,
    ) -> Product:
        slug = await generate_unique_slug(self.products, name)
        product = Product(id=uuid4(), slug=slug, name=name, model=model, variants=variants)
        initial_movements = [
            StockMovement(
                variant_id=variant_id,
                movement_type=MovementType.RESTOCK,
                quantity_delta=quantity,
            )
            for variant_id, quantity in (initial_quantities or {}).items()
            if quantity > 0
        ]
        register = RegisterStockedProductUseCase(
            products=self.products, movements=self.movements
        )
        return await register.execute(product, initial_movements=initial_movements)
