"""Use case: hard delete a product image.

Order is the OPPOSITE of upload (design.md Decision 5): the `product_images`
row is deleted FIRST, then the Storage object deletion is best-effort. The
row's removal is what determines the image's existence from the client's
perspective, so a Storage outage must never block a successful delete.
`ObjectStorage.delete` already treats a 404 as success (idempotent, see
`shared/application/object_storage.py`); any other, genuine
`ObjectStorageError` is swallowed here rather than surfaced, since the row
is already gone by the time it could occur.
"""

from dataclasses import dataclass
from uuid import UUID

from gcell.products.application.exceptions import ImageNotFoundError
from gcell.products.application.image_repository import ProductImageRepository
from gcell.shared.application.object_storage import ObjectStorage, ObjectStorageError


@dataclass
class DeleteProductImageUseCase:
    image_repository: ProductImageRepository
    object_storage: ObjectStorage

    async def execute(self, product_id: UUID, image_id: UUID) -> None:
        image = await self.image_repository.get_by_id(image_id)
        if image is None or image.product_id != product_id:
            # Never a 403 that would confirm existence across a wrong
            # parent (admin-product-images spec "Image Ownership Is
            # Checked At The Use-Case Layer").
            raise ImageNotFoundError(image_id, product_id)

        await self.image_repository.delete(image_id)

        try:
            await self.object_storage.delete(image.storage_path)
        except ObjectStorageError:
            # A non-404 Storage failure must not surface once the row is
            # gone -- the delete already succeeded from the client's
            # perspective (design.md Decision 5).
            pass
