"""Use case: register a new product in the catalog."""

from dataclasses import dataclass

from gcell.products.application.repository import ProductRepository
from gcell.products.domain.product import Product


@dataclass
class RegisterProductUseCase:
    """Registers a `Product` through the `ProductRepository` port.

    Kept intentionally small for this scaffold: it exists to prove the
    application layer wires domain objects to a repository port without
    depending on any framework or persistence technology.
    """

    repository: ProductRepository

    def execute(self, product: Product) -> Product:
        if self.repository.get_by_name(product.name) is not None:
            raise ValueError(f"Product '{product.name}' is already registered")
        self.repository.add(product)
        return product
