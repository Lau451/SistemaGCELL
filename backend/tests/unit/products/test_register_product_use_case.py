"""Unit tests for the products application layer (use case + in-memory repo).

Still framework-free: only `gcell.products.*` is imported.
"""

import pytest

from gcell.products.application.register_product import RegisterProductUseCase
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.in_memory_product_repository import (
    InMemoryProductRepository,
)


def make_product(name: str = "Funda transparente") -> Product:
    return Product(
        name=name,
        variants=[ProductVariant(phone_model="iPhone 13", price=45000.0, cost=30000.0)],
    )


def test_register_product_stores_it_in_the_repository() -> None:
    repository = InMemoryProductRepository()
    use_case = RegisterProductUseCase(repository=repository)

    result = use_case.execute(make_product())

    assert result.name == "Funda transparente"
    assert repository.get_by_name("Funda transparente") == result
    assert repository.list_all() == [result]


def test_register_product_rejects_duplicate_name() -> None:
    repository = InMemoryProductRepository()
    use_case = RegisterProductUseCase(repository=repository)
    use_case.execute(make_product())

    with pytest.raises(ValueError):
        use_case.execute(make_product())
