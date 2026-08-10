"""In-memory adapter for `ProductRepository`.

No real DB yet for this domain — this adapter satisfies the port with plain
dicts, keyed by `id` with a `slug` index, so the application layer can be
exercised end-to-end without Postgres wiring. Mirrors the `products_slug_key`
unique constraint by raising `DuplicateProductSlugError` on a slug collision,
the same exception type the future Postgres adapter translates
`UniqueViolationError` into — so `RegisterProductUseCase` stays
adapter-agnostic.
"""

from uuid import UUID

from gcell.products.application.exceptions import DuplicateProductSlugError
from gcell.products.domain.product import Product


class InMemoryProductRepository:
    def __init__(self) -> None:
        self._products_by_id: dict[UUID, Product] = {}
        self._ids_by_slug: dict[str, UUID] = {}

    async def add(self, product: Product) -> None:
        if product.slug in self._ids_by_slug:
            raise DuplicateProductSlugError(product.slug)
        self._products_by_id[product.id] = product
        self._ids_by_slug[product.slug] = product.id

    async def get_by_id(self, product_id: UUID) -> Product | None:
        return self._products_by_id.get(product_id)

    async def get_by_slug(self, slug: str) -> Product | None:
        product_id = self._ids_by_slug.get(slug)
        if product_id is None:
            return None
        return self._products_by_id.get(product_id)

    async def list_all(self) -> list[Product]:
        return list(self._products_by_id.values())
