"""Use case: upload a product image.

Sequence mirrors design.md's "Upload use-case sequence" exactly: resolve
the product (404 if unknown) -> resolve the variant ownership (404 if
`variant_id` belongs to a different product -- IDOR guard, use-case-layer
scan against the already-fetched aggregate, never a SQL join) -> size
check -> normalize -> derive `storage_path` -> `next_sort_order` ->
Storage `put` -> repository `add`. Storage write happens BEFORE the DB
insert (design.md Decision 4: "Storage object FIRST, DB row SECOND"); an
insert failure triggers exactly ONE compensating `ObjectStorage.delete`
of the just-written object before re-raising the original error
unmasked -- the `except BaseException` (not just `Exception`) also covers
a client-disconnect `CancelledError`.

Exception reconciliation (deferred from PR3, see
`shared/application/image_normalizer.py`'s module docstring): the
`shared/`-scoped `UnsupportedImageError`/`ImageTooLargeError` raised by
the `ImageNormalizer` port are caught here and re-raised as the
identically-shaped `products/`-scoped exceptions, so every caller
(routes, PR5) only ever needs to catch the `products/` exception types.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from gcell.products.application.exceptions import (
    ImageTooLargeError,
    ProductNotFoundError,
    UnsupportedImageError,
    VariantNotFoundError,
)
from gcell.products.application.image_path import build_storage_path
from gcell.products.application.image_repository import ProductImageRepository
from gcell.products.application.repository import ProductRepository
from gcell.products.domain.product_image import MAX_UPLOAD_BYTES, ProductImage
from gcell.shared.application.image_normalizer import ImageNormalizer
from gcell.shared.application.image_normalizer import (
    ImageTooLargeError as NormalizerImageTooLargeError,
)
from gcell.shared.application.image_normalizer import (
    UnsupportedImageError as NormalizerUnsupportedImageError,
)
from gcell.shared.application.object_storage import ObjectStorage


@dataclass
class UploadProductImageUseCase:
    image_repository: ProductImageRepository
    product_repository: ProductRepository
    object_storage: ObjectStorage
    normalizer: ImageNormalizer

    async def execute(
        self,
        product_id: UUID,
        data: bytes,
        variant_id: UUID | None,
        alt_text: str | None,
    ) -> ProductImage:
        product = await self.product_repository.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)

        color: str | None = None
        if variant_id is not None:
            variant = next((v for v in product.variants if v.id == variant_id), None)
            if variant is None:
                raise VariantNotFoundError(variant_id, product_id)
            color = variant.color

        if len(data) > MAX_UPLOAD_BYTES:
            raise ImageTooLargeError(len(data), MAX_UPLOAD_BYTES)

        try:
            normalized = self.normalizer.normalize(data)
        except NormalizerUnsupportedImageError as exc:
            raise UnsupportedImageError(exc.reason) from exc
        except NormalizerImageTooLargeError as exc:
            raise ImageTooLargeError(exc.size, exc.max_size) from exc

        image_id = uuid4()
        storage_path = build_storage_path(product.slug, color, image_id)
        sort_order = await self.image_repository.next_sort_order(product_id, variant_id)

        await self.object_storage.put(storage_path, normalized.data, normalized.content_type)

        image = ProductImage(
            id=image_id,
            product_id=product_id,
            variant_id=variant_id,
            storage_path=storage_path,
            alt_text=alt_text,
            sort_order=sort_order,
        )
        try:
            await self.image_repository.add(image)
        except BaseException:
            await self.object_storage.delete(storage_path)
            raise
        return image
