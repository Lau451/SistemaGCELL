"""Unit tests for `CreateProductUseCase` -- slug derivation + collision
resolution, wrapping (not replacing) `RegisterProductUseCase`.
"""

from decimal import Decimal
from uuid import uuid4

from gcell.products.domain.product import ProductVariant
from gcell.products.infrastructure.in_memory_product_repository import (
    InMemoryProductRepository,
)


def make_variant(color: str = "Negro") -> ProductVariant:
    return ProductVariant(
        id=uuid4(), color=color, price=Decimal("45000.00"), cost=Decimal("30000.00")
    )


async def test_execute_derives_a_slug_from_the_name() -> None:
    from gcell.products.application.create_product import CreateProductUseCase

    repository = InMemoryProductRepository()
    use_case = CreateProductUseCase(repository=repository)

    product = await use_case.execute(
        name="iPhone 15", model="iPhone 15", variants=[make_variant()]
    )

    assert product.slug == "iphone-15"
    assert product.name == "iPhone 15"


async def test_execute_persists_the_product_through_the_repository() -> None:
    from gcell.products.application.create_product import CreateProductUseCase

    repository = InMemoryProductRepository()
    use_case = CreateProductUseCase(repository=repository)

    product = await use_case.execute(
        name="iPhone 15", model="iPhone 15", variants=[make_variant()]
    )

    assert await repository.get_by_id(product.id) == product
    assert await repository.get_by_slug("iphone-15") == product


async def test_execute_resolves_a_name_collision_with_a_numeric_suffix() -> None:
    from gcell.products.application.create_product import CreateProductUseCase

    repository = InMemoryProductRepository()
    use_case = CreateProductUseCase(repository=repository)
    first = await use_case.execute(
        name="iPhone 15", model="iPhone 15", variants=[make_variant()]
    )

    second = await use_case.execute(
        name="iPhone 15", model="iPhone 15", variants=[make_variant("Rojo")]
    )

    assert first.slug == "iphone-15"
    assert second.slug == "iphone-15-2"
    assert first.id != second.id
