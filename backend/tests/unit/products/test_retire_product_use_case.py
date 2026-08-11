"""Unit tests for `RetireProductUseCase` and `RetireVariantUseCase`.

Q4 decision (design.md): retiring the LAST remaining active variant of a
product MUST succeed and MUST NOT retire the product -- no "must keep >=1
variant" invariant anywhere.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from gcell.products.application.exceptions import (
    ProductNotFoundError,
    VariantNotFoundError,
)
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.in_memory_product_repository import (
    InMemoryProductRepository,
)


def make_variant(color: str = "Negro") -> ProductVariant:
    return ProductVariant(
        id=uuid4(), color=color, price=Decimal("45000.00"), cost=Decimal("30000.00")
    )


async def make_persisted_product(
    repository: InMemoryProductRepository, *, variants: list[ProductVariant] | None = None
) -> Product:
    product = Product(
        id=uuid4(),
        slug=f"iphone-15-{uuid4().hex[:6]}",
        name="iPhone 15",
        model="iPhone 15",
        variants=variants if variants is not None else [make_variant()],
    )
    await repository.add(product)
    return product


async def test_retiring_a_product_marks_it_no_longer_active() -> None:
    from gcell.products.application.retire_product import RetireProductUseCase

    repository = InMemoryProductRepository()
    product = await make_persisted_product(repository)
    use_case = RetireProductUseCase(repository=repository)

    await use_case.execute(product.id)

    assert await repository.get_by_id(product.id) is None


async def test_retiring_an_unknown_product_raises_product_not_found() -> None:
    from gcell.products.application.retire_product import RetireProductUseCase

    repository = InMemoryProductRepository()
    use_case = RetireProductUseCase(repository=repository)

    with pytest.raises(ProductNotFoundError):
        await use_case.execute(uuid4())


async def test_retiring_a_variant_leaves_the_product_and_siblings_active() -> None:
    from gcell.products.application.retire_product import RetireVariantUseCase

    repository = InMemoryProductRepository()
    variant_a = make_variant("Negro")
    variant_b = make_variant("Rojo")
    product = await make_persisted_product(repository, variants=[variant_a, variant_b])
    use_case = RetireVariantUseCase(repository=repository)

    await use_case.execute(product_id=product.id, variant_id=variant_a.id)

    persisted = await repository.get_by_id(product.id)
    assert persisted is not None
    variant_ids = {variant.id for variant in persisted.variants}
    assert variant_a.id not in variant_ids
    assert variant_b.id in variant_ids


async def test_retiring_the_last_variant_succeeds_and_does_not_retire_the_product() -> (
    None
):
    from gcell.products.application.retire_product import RetireVariantUseCase

    repository = InMemoryProductRepository()
    only_variant = make_variant()
    product = await make_persisted_product(repository, variants=[only_variant])
    use_case = RetireVariantUseCase(repository=repository)

    await use_case.execute(product_id=product.id, variant_id=only_variant.id)

    persisted = await repository.get_by_id(product.id)
    assert persisted is not None
    assert persisted.variants == []


async def test_retiring_a_variant_of_another_product_raises_variant_not_found() -> None:
    from gcell.products.application.retire_product import RetireVariantUseCase

    repository = InMemoryProductRepository()
    product_a = await make_persisted_product(repository)
    product_b = await make_persisted_product(repository)
    use_case = RetireVariantUseCase(repository=repository)

    with pytest.raises(VariantNotFoundError):
        await use_case.execute(
            product_id=product_a.id, variant_id=product_b.variants[0].id
        )
