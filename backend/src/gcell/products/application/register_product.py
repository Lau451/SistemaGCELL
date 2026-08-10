"""Use case: register a new product in the catalog."""

from dataclasses import dataclass

from gcell.products.application.repository import ProductRepository
from gcell.products.domain.product import Product


@dataclass
class RegisterProductUseCase:
    """Registers a `Product` through the `ProductRepository` port.

    Duplicate-slug detection is NOT pre-checked here (that would be a
    TOCTOU-racy extra round trip that duplicates the rule in two places).
    `repository.add` is the single source of truth: it raises
    `DuplicateProductSlugError` on a slug conflict, whether translated from a
    real DB constraint (Postgres adapter) or checked directly (in-memory
    adapter) — see `design.md` "duplicate slug via constraint translation".
    """

    repository: ProductRepository

    async def execute(self, product: Product) -> Product:
        await self.repository.add(product)
        return product
