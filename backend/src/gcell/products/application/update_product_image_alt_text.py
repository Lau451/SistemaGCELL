"""Use case: update an existing image's `alt_text`, independently of
re-uploading the image file (design.md DD3).

Reproduces `DeleteProductImageUseCase`/`ReorderProductImageUseCase`'s
ownership guard verbatim: `get_by_id` -> `image is None or image.product_id
!= product_id` -> `ImageNotFoundError` -> 404 `not_found` via the existing
`_execute_or_raise`, never a 403 that would confirm a cross-parent image's
existence (admin-product-images spec "Alt-text update on another product's
image is rejected").

`alt_text` is a required argument (`str | None`, no default) -- an explicit
`None`, or a value that is blank after stripping, clears the column (the
only way to undo bad alt text). A non-blank value is stored stripped.
"""

from dataclasses import dataclass, replace
from uuid import UUID

from gcell.products.application.exceptions import ImageNotFoundError
from gcell.products.application.image_repository import ProductImageRepository
from gcell.products.domain.product_image import ProductImage


def _normalize(alt_text: str | None) -> str | None:
    if alt_text is None:
        return None
    stripped = alt_text.strip()
    return stripped or None


@dataclass
class UpdateProductImageAltTextUseCase:
    image_repository: ProductImageRepository

    async def execute(
        self, product_id: UUID, image_id: UUID, alt_text: str | None
    ) -> ProductImage:
        image = await self.image_repository.get_by_id(image_id)
        if image is None or image.product_id != product_id:
            # Never a 403 that would confirm existence across a wrong
            # parent (admin-product-images spec, and design's
            # Threat-Matrix IDOR row).
            raise ImageNotFoundError(image_id, product_id)

        normalized = _normalize(alt_text)
        await self.image_repository.update_alt_text(image_id, normalized)
        return replace(image, alt_text=normalized)
