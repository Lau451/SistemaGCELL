"""In-memory adapter for `ProductImageRepository`.

Own dict store, keyed by `id` -- images are a separate aggregate (design.md
Decision 1), so this adapter has no visibility into `product_variants`
soft-delete state the way `PostgresProductImageRepository.list_for_product`'s
join does. That is fine: the product-persistence spec's "adapters agree on
image operations" requirement is scoped to insert/reorder/delete producing
the same final state, not to the variant-soft-delete-hides-images
requirement, which is a Postgres-only, cross-table concern this adapter is
never asked to replicate.

`delete` is a genuine HARD delete -- pops the dict entry, never marks a
tombstone -- matching the Postgres adapter's real `DELETE`.
"""

from dataclasses import replace
from uuid import UUID

from gcell.products.application.exceptions import ImageNotFoundError
from gcell.products.domain.product_image import ProductImage


class InMemoryProductImageRepository:
    def __init__(self) -> None:
        self._images_by_id: dict[UUID, ProductImage] = {}

    async def add(self, image: ProductImage) -> None:
        self._images_by_id[image.id] = image

    async def get_by_id(self, image_id: UUID) -> ProductImage | None:
        return self._images_by_id.get(image_id)

    async def list_for_product(self, product_id: UUID) -> list[ProductImage]:
        images = [image for image in self._images_by_id.values() if image.product_id == product_id]
        return sorted(images, key=lambda image: (image.sort_order, str(image.id)))

    async def delete(self, image_id: UUID) -> None:
        if image_id not in self._images_by_id:
            raise ImageNotFoundError(image_id)
        del self._images_by_id[image_id]

    async def next_sort_order(self, product_id: UUID, variant_id: UUID | None) -> int:
        group_orders = [
            image.sort_order
            for image in self._images_by_id.values()
            if image.product_id == product_id and image.variant_id == variant_id
        ]
        return max(group_orders, default=-1) + 1

    async def reorder(self, product_id: UUID, ordered_image_ids: list[UUID]) -> None:
        for sort_order, image_id in enumerate(ordered_image_ids):
            image = self._images_by_id.get(image_id)
            if image is None or image.product_id != product_id:
                continue
            self._images_by_id[image_id] = ProductImage(
                id=image.id,
                product_id=image.product_id,
                variant_id=image.variant_id,
                storage_path=image.storage_path,
                alt_text=image.alt_text,
                sort_order=sort_order,
            )

    async def update_alt_text(self, image_id: UUID, alt_text: str | None) -> None:
        image = self._images_by_id.get(image_id)
        if image is None:
            raise ImageNotFoundError(image_id)
        self._images_by_id[image_id] = replace(image, alt_text=alt_text)
