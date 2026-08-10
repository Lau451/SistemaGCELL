"""Repository port for the products domain.

Defined in `application/` (not `domain/`) because it is a boundary
contract the application layer depends on and infrastructure adapters
implement — the domain model itself has no notion of persistence.
"""

from typing import Protocol
from uuid import UUID

from gcell.products.domain.product import Product


class ProductRepository(Protocol):
    """Port implemented by infrastructure adapters (in-memory, DB, ...).

    Keyed by `slug` — the only DB-unique business identifier — not `name`.
    `get_by_name` does not exist: it would encourage lookups/duplicate
    checks against a non-unique field.
    """

    async def add(self, product: Product) -> None: ...

    async def get_by_id(self, product_id: UUID) -> Product | None: ...

    async def get_by_slug(self, slug: str) -> Product | None: ...

    async def list_all(self) -> list[Product]: ...
