"""In-memory adapter for `ProductRepository`.

No real DB yet for this domain — this adapter satisfies the port with plain
dicts, keyed by `id` with a `slug` index, so the application layer can be
exercised end-to-end without Postgres wiring. Mirrors the `products_slug_key`
unique constraint by raising `DuplicateProductSlugError` on a slug collision,
the same exception type the future Postgres adapter translates
`UniqueViolationError` into — so `RegisterProductUseCase` stays
adapter-agnostic.

Soft-delete is mirrored with a `_deleted: set[UUID]` of retired product ids
-- never a real row deletion, matching the Postgres adapter's `UPDATE ...
SET deleted_at`. `slug_exists` deliberately does NOT consult `_deleted`: a
retired product's slug must still read as "taken" (design.md "retired slugs
stay reserved"), the same way the DB's global unique index behaves.
"""

from uuid import UUID

from gcell.products.application.exceptions import (
    DuplicateProductSlugError,
    ProductNotFoundError,
    VariantNotFoundError,
)
from gcell.products.domain.product import Product


class InMemoryProductRepository:
    def __init__(self) -> None:
        self._products_by_id: dict[UUID, Product] = {}
        self._ids_by_slug: dict[str, UUID] = {}
        self._deleted: set[UUID] = set()

    async def add(self, product: Product) -> None:
        if product.slug in self._ids_by_slug:
            raise DuplicateProductSlugError(product.slug)
        self._products_by_id[product.id] = product
        self._ids_by_slug[product.slug] = product.id

    async def get_by_id(self, product_id: UUID) -> Product | None:
        if product_id in self._deleted:
            return None
        return self._products_by_id.get(product_id)

    async def get_by_slug(self, slug: str) -> Product | None:
        product_id = self._ids_by_slug.get(slug)
        if product_id is None or product_id in self._deleted:
            return None
        return self._products_by_id.get(product_id)

    async def list_all(self) -> list[Product]:
        return [
            product
            for product in self._products_by_id.values()
            if product.id not in self._deleted
        ]

    async def update(self, product: Product) -> None:
        """Field edit + add/update variants. Never deletes a variant, never
        touches `slug` (the incoming `product.slug` is ignored -- the
        persisted slug is frozen at creation).
        """
        if product.id not in self._products_by_id or product.id in self._deleted:
            raise ProductNotFoundError(product.id)
        existing = self._products_by_id[product.id]
        variants_by_id = {variant.id: variant for variant in existing.variants}
        for variant in product.variants:
            variants_by_id[variant.id] = variant
        self._products_by_id[existing.id] = Product(
            id=existing.id,
            slug=existing.slug,
            name=product.name,
            model=product.model,
            variants=list(variants_by_id.values()),
        )

    async def soft_delete(self, product_id: UUID) -> None:
        if product_id not in self._products_by_id or product_id in self._deleted:
            raise ProductNotFoundError(product_id)
        self._deleted.add(product_id)

    async def soft_delete_variant(self, product_id: UUID, variant_id: UUID) -> None:
        product = self._products_by_id.get(product_id)
        if product is None or product_id in self._deleted:
            raise VariantNotFoundError(variant_id, product_id)
        if not any(variant.id == variant_id for variant in product.variants):
            raise VariantNotFoundError(variant_id, product_id)
        remaining = [
            variant for variant in product.variants if variant.id != variant_id
        ]
        self._products_by_id[product_id] = Product(
            id=product.id,
            slug=product.slug,
            name=product.name,
            model=product.model,
            variants=remaining,
        )

    async def slug_exists(self, slug: str) -> bool:
        return slug in self._ids_by_slug
