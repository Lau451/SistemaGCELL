"""Unit tests for the products application layer (use case + in-memory repo).

Still framework-free: only `gcell.products.*` is imported.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from gcell.products.application.exceptions import DuplicateProductSlugError
from gcell.products.application.register_product import RegisterProductUseCase
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.in_memory_product_repository import (
    InMemoryProductRepository,
)


def make_product(
    slug: str = "iphone-13-funda", name: str = "Funda transparente"
) -> Product:
    return Product(
        id=uuid4(),
        slug=slug,
        name=name,
        model="iPhone 13",
        variants=[
            ProductVariant(
                id=uuid4(),
                color="Negro",
                price=Decimal("45000.00"),
                cost=Decimal("30000.00"),
            )
        ],
    )


async def test_register_product_stores_it_in_the_repository() -> None:
    repository = InMemoryProductRepository()
    use_case = RegisterProductUseCase(repository=repository)

    result = await use_case.execute(make_product())

    assert result.name == "Funda transparente"
    assert await repository.get_by_slug("iphone-13-funda") == result
    assert await repository.list_all() == [result]


async def test_register_product_rejects_duplicate_slug() -> None:
    repository = InMemoryProductRepository()
    use_case = RegisterProductUseCase(repository=repository)
    await use_case.execute(make_product(slug="iphone-13-funda"))

    with pytest.raises(DuplicateProductSlugError):
        await use_case.execute(
            make_product(slug="iphone-13-funda", name="Otra funda")
        )


async def test_register_product_allows_zero_variants() -> None:
    repository = InMemoryProductRepository()
    use_case = RegisterProductUseCase(repository=repository)
    product = Product(
        id=uuid4(),
        slug="sin-variantes",
        name="Sin variantes",
        model="iPhone 13",
        variants=[],
    )

    result = await use_case.execute(product)

    assert result.variants == []


async def test_get_by_id_returns_persisted_product() -> None:
    repository = InMemoryProductRepository()
    use_case = RegisterProductUseCase(repository=repository)
    result = await use_case.execute(make_product())

    assert await repository.get_by_id(result.id) == result


async def test_get_by_slug_returns_none_for_unknown_slug() -> None:
    repository = InMemoryProductRepository()

    assert await repository.get_by_slug("no-existe") is None
