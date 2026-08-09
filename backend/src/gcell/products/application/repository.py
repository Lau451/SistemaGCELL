"""Repository port for the products domain.

Defined in `application/` (not `domain/`) because it is a boundary
contract the application layer depends on and infrastructure adapters
implement — the domain model itself has no notion of persistence.
"""

from typing import Protocol

from gcell.products.domain.product import Product


class ProductRepository(Protocol):
    """Port implemented by infrastructure adapters (in-memory, DB, ...)."""

    def add(self, product: Product) -> None: ...

    def get_by_name(self, name: str) -> Product | None: ...

    def list_all(self) -> list[Product]: ...
