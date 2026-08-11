"""Unit tests for `UpdateProductUseCase` -- field edit + variant add/update,
never touches `slug`, never deletes a variant.
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


async def make_persisted_product(repository: InMemoryProductRepository) -> Product:
    product = Product(
        id=uuid4(),
        slug="iphone-15",
        name="iPhone 15",
        model="iPhone 15",
        variants=[make_variant()],
    )
    await repository.add(product)
    return product


async def test_rename_does_not_change_the_slug() -> None:
    from gcell.products.application.update_product import UpdateProductUseCase

    repository = InMemoryProductRepository()
    product = await make_persisted_product(repository)
    use_case = UpdateProductUseCase(repository=repository)

    updated = await use_case.execute(
        product_id=product.id,
        name="iPhone 15 Pro",
        model="iPhone 15 Pro",
        variants=[],
    )

    assert updated.slug == "iphone-15"
    assert updated.name == "iPhone 15 Pro"
    persisted = await repository.get_by_id(product.id)
    assert persisted is not None
    assert persisted.slug == "iphone-15"


async def test_update_on_a_retired_product_raises_product_not_found() -> None:
    from gcell.products.application.update_product import UpdateProductUseCase

    repository = InMemoryProductRepository()
    product = await make_persisted_product(repository)
    await repository.soft_delete(product.id)
    use_case = UpdateProductUseCase(repository=repository)

    with pytest.raises(ProductNotFoundError):
        await use_case.execute(
            product_id=product.id, name="X", model="X", variants=[]
        )


async def test_update_on_an_unknown_product_raises_product_not_found() -> None:
    from gcell.products.application.update_product import UpdateProductUseCase

    repository = InMemoryProductRepository()
    use_case = UpdateProductUseCase(repository=repository)

    with pytest.raises(ProductNotFoundError):
        await use_case.execute(
            product_id=uuid4(), name="X", model="X", variants=[]
        )


async def test_variant_belonging_to_a_different_product_raises_variant_not_found() -> (
    None
):
    from gcell.products.application.update_product import UpdateProductUseCase

    repository = InMemoryProductRepository()
    product_a = await make_persisted_product(repository)
    product_b = Product(
        id=uuid4(),
        slug="iphone-15-2",
        name="iPhone 15",
        model="iPhone 15",
        variants=[make_variant("Rojo")],
    )
    await repository.add(product_b)
    use_case = UpdateProductUseCase(repository=repository)
    foreign_variant = product_b.variants[0]

    with pytest.raises(VariantNotFoundError):
        await use_case.execute(
            product_id=product_a.id,
            name=product_a.name,
            model=product_a.model,
            variants=[foreign_variant],
        )


async def test_a_genuinely_new_variant_is_added() -> None:
    from gcell.products.application.update_product import UpdateProductUseCase

    repository = InMemoryProductRepository()
    product = await make_persisted_product(repository)
    use_case = UpdateProductUseCase(repository=repository)
    new_variant = make_variant("Azul")

    updated = await use_case.execute(
        product_id=product.id,
        name=product.name,
        model=product.model,
        variants=[new_variant],
    )

    variant_ids = {variant.id for variant in updated.variants}
    assert new_variant.id in variant_ids
    assert product.variants[0].id in variant_ids


async def test_an_existing_variant_of_this_product_is_updated_in_place() -> None:
    from gcell.products.application.update_product import UpdateProductUseCase

    repository = InMemoryProductRepository()
    product = await make_persisted_product(repository)
    use_case = UpdateProductUseCase(repository=repository)
    edited_variant = ProductVariant(
        id=product.variants[0].id,
        color="Negro Mate",
        price=Decimal("50000.00"),
        cost=Decimal("35000.00"),
    )

    updated = await use_case.execute(
        product_id=product.id,
        name=product.name,
        model=product.model,
        variants=[edited_variant],
    )

    assert len(updated.variants) == 1
    assert updated.variants[0].color == "Negro Mate"
