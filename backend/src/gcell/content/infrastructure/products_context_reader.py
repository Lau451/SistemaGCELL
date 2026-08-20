"""Products-backed adapter for `ProductContextReader` (design.md DD2).

Delegates to `ProductRepository`/`ProductImageRepository` -- issues no SQL
of its own (D4 satisfied literally: this module has zero DB-driver imports).
Injected at the composition root in `api/admin.py` (wired starting PR 11);
this PR ships the adapter unwired, exercised only by its own unit tests
against the in-memory product/image repositories.
"""

from uuid import UUID

from gcell.content.application.product_context_reader import (
    ProductCopyContext,
    ProductPhotoContext,
)
from gcell.products.application.image_repository import ProductImageRepository
from gcell.products.application.repository import ProductRepository


class ProductsContextReader:
    """`ProductContextReader` implementation over the `products` domain's
    own read-only repository methods (`get_by_id`, `list_for_product`).
    """

    def __init__(
        self,
        product_repository: ProductRepository,
        image_repository: ProductImageRepository,
    ) -> None:
        self._products = product_repository
        self._images = image_repository

    async def product_context(self, product_id: UUID) -> ProductCopyContext | None:
        product = await self._products.get_by_id(product_id)
        if product is None:
            return None
        return ProductCopyContext(
            name=product.name,
            model=product.model,
            colors=[variant.color for variant in product.variants],
        )

    async def photo_context(
        self, product_id: UUID, image_id: UUID
    ) -> ProductPhotoContext | None:
        product = await self._products.get_by_id(product_id)
        if product is None:
            return None

        # Ownership via query scope (DD2): `image_id` is only resolved
        # from THIS product's own image list, never fetched directly by
        # id -- so a cross-parent image id can never match here, and no
        # separate `image.product_id != product_id` predicate is needed.
        images = await self._images.list_for_product(product_id)
        image = next((candidate for candidate in images if candidate.id == image_id), None)
        if image is None:
            return None

        variant_color: str | None = None
        if image.variant_id is not None:
            variant = next(
                (v for v in product.variants if v.id == image.variant_id), None
            )
            variant_color = variant.color if variant is not None else None

        return ProductPhotoContext(
            storage_path=image.storage_path,
            product_name=product.name,
            product_model=product.model,
            variant_color=variant_color,
        )
