"""Repository port for product images.

Own aggregate, own port (see design.md Decision 1 -- images are a SEPARATE
aggregate, not a `Product`/`ProductVariant` field). Defined in
`application/` for the same boundary reason as `ProductRepository`: the
domain model itself has no notion of persistence.
"""

from typing import Protocol
from uuid import UUID

from gcell.products.domain.product_image import ProductImage


class ProductImageRepository(Protocol):
    """Port implemented by infrastructure adapters (in-memory, Postgres)."""

    async def add(self, image: ProductImage) -> None: ...

    async def get_by_id(self, image_id: UUID) -> ProductImage | None: ...

    async def list_for_product(self, product_id: UUID) -> list[ProductImage]:
        """List a product's images, ordered by `sort_order`.

        MUST hide any image whose `variant_id` references a soft-deleted
        variant -- the composite FK does not cascade on a soft delete
        (`UPDATE ... SET deleted_at`, never a row removal), so this is a
        read-time filter, mirroring the read-time soft-delete cascade
        already applied to variant rows themselves (see product-
        persistence spec "Images Of A Soft-Deleted Variant Are Hidden At
        Read Time"). Hero images (`variant_id IS NULL`) are always
        included, regardless of any variant's state.
        """
        ...

    async def delete(self, image_id: UUID) -> None:
        """HARD delete -- unlike products/variants, images carry no
        order-integrity concern (see proposal.md decision 2). Raises
        `ImageNotFoundError` if zero rows were affected.
        """
        ...

    async def next_sort_order(self, product_id: UUID, variant_id: UUID | None) -> int:
        """The next `sort_order` for the group identified by
        `(product_id, variant_id)` -- the hero group (`variant_id IS
        NULL`) and each variant's group are independent sequences.
        """
        ...

    async def reorder(self, product_id: UUID, ordered_image_ids: list[UUID]) -> None:
        """Persist `sort_order` 0..n-1 matching `ordered_image_ids`'
        position, atomically, scoped to `product_id`.

        Does NOT validate that the list is a full/exact permutation of
        the product's images -- that ownership/completeness precondition
        is a use-case-layer concern (design.md Decision 6), not this
        port's.
        """
        ...

    async def update_alt_text(self, image_id: UUID, alt_text: str | None) -> None:
        """Persist a new `alt_text` value, changing no other column
        (design.md DD3). Raises `ImageNotFoundError` if zero rows were
        affected -- same zero-rows-affected contract as `delete`. Ownership
        (does `image_id` belong to the caller's product) is a use-case-
        layer concern (`UpdateProductImageAltTextUseCase`), not this
        port's -- this method trusts its caller already resolved that.
        """
        ...
