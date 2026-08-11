"""Use cases: retire (soft-delete) a product or a single variant.

Product retirement cascades to its variants at READ time (every read joins
on `deleted_at IS NULL`) -- it is a single row `UPDATE`, never a second
write against `product_variants`. See design.md "product retirement
cascades at read time, not by stamping variants".

Retiring the LAST remaining active variant of a product MUST succeed and
MUST NOT retire the product (proposal Q4) -- neither use case here enforces
any "at least one active variant" invariant; each is a thin, direct
delegation to its matching repository port method.
"""

from dataclasses import dataclass
from uuid import UUID

from gcell.products.application.repository import ProductRepository


@dataclass
class RetireProductUseCase:
    """Retires a product. Cascades to its variants via the read-time
    filter, never a second write. Raises `ProductNotFoundError` if no
    ACTIVE product with that id exists (propagated from the port).
    """

    repository: ProductRepository

    async def execute(self, product_id: UUID) -> None:
        await self.repository.soft_delete(product_id)


@dataclass
class RetireVariantUseCase:
    """Retires a single variant of `product_id`. Never affects the product
    or sibling variants -- including when this is the product's last
    active variant (Q4: zero active variants is a valid, listable state).
    Raises `VariantNotFoundError` for an unknown/cross-parent/already-
    retired variant (propagated from the port).
    """

    repository: ProductRepository

    async def execute(self, product_id: UUID, variant_id: UUID) -> None:
        await self.repository.soft_delete_variant(product_id, variant_id)
