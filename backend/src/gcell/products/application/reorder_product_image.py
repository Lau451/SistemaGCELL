"""Use case: replace a product's whole image order in one call.

The submitted list MUST be exactly a permutation of the product's own
image ids (design.md Decision 6: a dedicated `PUT .../images/order` with
the full ordered list, never a partial/delta payload). Any foreign id,
any repeated id, or any id the product owns but that is missing from the
submitted list is rejected as not-found -- scoped by a set comparison
against an already-fetched, product-scoped list (the same use-case-layer
IDOR pattern as every other image use case, never a SQL join) -- with
zero writes to the repository.
"""

from dataclasses import dataclass
from uuid import UUID

from gcell.products.application.exceptions import ImageNotFoundError
from gcell.products.application.image_repository import ProductImageRepository
from gcell.products.domain.product_image import ProductImage


@dataclass
class ReorderProductImageUseCase:
    image_repository: ProductImageRepository

    async def execute(
        self, product_id: UUID, ordered_image_ids: list[UUID]
    ) -> list[ProductImage]:
        existing = await self.image_repository.list_for_product(product_id)
        existing_ids = {image.id for image in existing}

        foreign_ids = [
            image_id for image_id in ordered_image_ids if image_id not in existing_ids
        ]
        if foreign_ids:
            raise ImageNotFoundError(foreign_ids[0], product_id)

        missing_ids = existing_ids - set(ordered_image_ids)
        if missing_ids or len(ordered_image_ids) != len(existing_ids):
            # Either a genuinely omitted id, or the list is not an exact
            # permutation (e.g. a repeated id papering over a missing
            # one) -- either way, reject as not-found before any write.
            reported_id = next(iter(missing_ids), None) or ordered_image_ids[0]
            raise ImageNotFoundError(reported_id, product_id)

        await self.image_repository.reorder(product_id, ordered_image_ids)
        return await self.image_repository.list_for_product(product_id)
