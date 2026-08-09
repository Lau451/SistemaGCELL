"""In-memory adapter for `ProductRepository`.

No real DB yet — this scaffold-stage adapter satisfies the port with a
plain dict so the application layer can be exercised end-to-end without
Supabase/SQLAlchemy wiring, which does not exist yet in this change.
"""

from gcell.products.domain.product import Product


class InMemoryProductRepository:
    def __init__(self) -> None:
        self._products: dict[str, Product] = {}

    def add(self, product: Product) -> None:
        self._products[product.name] = product

    def get_by_name(self, name: str) -> Product | None:
        return self._products.get(name)

    def list_all(self) -> list[Product]:
        return list(self._products.values())
