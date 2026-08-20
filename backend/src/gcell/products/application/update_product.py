"""Use case: edit a product's fields and add/update its variants.

Never touches `slug` (frozen at creation, see design.md "PATCH never
retires; retirement has its own URL") and never deletes a variant --
variant retirement is `RetireVariantUseCase`'s job, its own explicit,
effect-idempotent operation.
"""

from dataclasses import dataclass
from uuid import UUID

from gcell.products.application.exceptions import (
    ProductNotFoundError,
    VariantNotFoundError,
)
from gcell.products.application.repository import ProductRepository
from gcell.products.domain.product import Product, ProductVariant


@dataclass
class UpdateProductUseCase:
    """Persists `name`/`model` edits and reconciles `variants` (adds any
    id not yet known anywhere, updates any id that belongs to THIS
    product) in one atomic `repository.update` call.

    A variant id that already exists but belongs to a DIFFERENT product
    raises `VariantNotFoundError` -- the IDOR guard: never silently
    reparent or mutate another product's variant (see design.md's threat
    matrix, "IDOR across parents").
    """

    repository: ProductRepository

    async def execute(
        self,
        product_id: UUID,
        name: str,
        model: str,
        variants: list[ProductVariant],
        description: str | None = None,
        short_description: str | None = None,
    ) -> Product:
        existing = await self.repository.get_by_id(product_id)
        if existing is None:
            raise ProductNotFoundError(product_id)

        if variants:
            all_products = await self.repository.list_all()
            variant_owner_id: dict[UUID, UUID] = {
                variant.id: product.id
                for product in all_products
                for variant in product.variants
            }
            for variant in variants:
                owner_id = variant_owner_id.get(variant.id)
                if owner_id is not None and owner_id != product_id:
                    raise VariantNotFoundError(variant.id, product_id)

        to_persist = Product(
            id=existing.id,
            slug=existing.slug,
            name=name,
            model=model,
            variants=variants,
            description=description,
            short_description=short_description,
        )
        await self.repository.update(to_persist)

        merged_variants = {variant.id: variant for variant in existing.variants}
        for variant in variants:
            merged_variants[variant.id] = variant
        return Product(
            id=existing.id,
            slug=existing.slug,
            name=name,
            model=model,
            variants=list(merged_variants.values()),
            description=description,
            short_description=short_description,
        )
