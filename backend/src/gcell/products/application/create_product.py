"""Use case: create a new product with a server-derived slug.

Wraps (does not replace or modify) `RegisterProductUseCase` -- slug
derivation is the only new concern here; persistence itself, including
duplicate-slug-at-insert handling, stays owned by `RegisterProductUseCase`
and `repository.add`. See design.md "slug generated in application/,
validated only by the domain".
"""

from dataclasses import dataclass
from uuid import uuid4

from gcell.products.application.register_product import RegisterProductUseCase
from gcell.products.application.repository import ProductRepository
from gcell.products.application.slug import generate_unique_slug
from gcell.products.domain.product import Product, ProductVariant


@dataclass
class CreateProductUseCase:
    """Derives a slug from `name`, then delegates persistence to
    `RegisterProductUseCase`. The domain's `Product.__post_init__` is the
    final authority: it re-validates whatever `generate_unique_slug`
    produces.
    """

    repository: ProductRepository

    async def execute(
        self,
        name: str,
        model: str,
        variants: list[ProductVariant],
        description: str | None = None,
        short_description: str | None = None,
    ) -> Product:
        slug = await generate_unique_slug(self.repository, name)
        product = Product(
            id=uuid4(),
            slug=slug,
            name=name,
            model=model,
            variants=variants,
            description=description,
            short_description=short_description,
        )
        register = RegisterProductUseCase(repository=self.repository)
        return await register.execute(product)
