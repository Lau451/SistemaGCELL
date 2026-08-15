"""Unit tests for `RecordVariantStockMovementUseCase`.

Fakes/spies only (`InMemoryProductRepository` + `InMemoryStockMovementRepository`),
same convention as `test_upload_product_image_use_case.py`. Proves the
ownership guard (design.md Decision 1 / Interfaces-Contracts) runs BEFORE
`record_movement.execute` is ever called -- an unknown product, a variant
owned by another product, and a soft-deleted variant (absent from
`product.variants`, since `get_by_id` already filters `deleted_at IS NULL`)
must all raise before any write, and the happy path must delegate every
argument verbatim (spec: admin-stock-management "Movement Ownership Is
Checked Before Any Write").
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from gcell.products.application.exceptions import ProductNotFoundError, VariantNotFoundError
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.in_memory_product_repository import (
    InMemoryProductRepository,
)
from gcell.stock.application.record_stock_movement import RecordStockMovementUseCase
from gcell.stock.domain.stock_movement import MovementType
from gcell.stock.infrastructure.in_memory_stock_movement_repository import (
    InMemoryStockMovementRepository,
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
        slug=f"funda-iphone-15-{uuid4().hex[:8]}",
        name="Funda iPhone 15",
        model="Funda iPhone 15",
        variants=variants if variants is not None else [make_variant()],
    )
    await repository.add(product)
    return product


def make_use_case(
    *,
    product_repository: InMemoryProductRepository | None = None,
    movement_repository: InMemoryStockMovementRepository | None = None,
):
    from gcell.stock.application.record_variant_stock_movement import (
        RecordVariantStockMovementUseCase,
    )

    movements = movement_repository or InMemoryStockMovementRepository()
    use_case = RecordVariantStockMovementUseCase(
        products=product_repository or InMemoryProductRepository(),
        record_movement=RecordStockMovementUseCase(repository=movements),
    )
    return use_case, movements


async def test_unknown_product_raises_product_not_found_before_any_record_call() -> None:
    use_case, movements = make_use_case()

    with pytest.raises(ProductNotFoundError):
        await use_case.execute(
            product_id=uuid4(), variant_id=uuid4(), movement_type="restock", quantity_delta=5
        )

    assert movements.recorded == []


async def test_variant_owned_by_another_product_raises_variant_not_found_before_record() -> (
    None
):
    product_repository = InMemoryProductRepository()
    product = await make_persisted_product(product_repository)
    other_product = await make_persisted_product(product_repository)
    use_case, movements = make_use_case(product_repository=product_repository)

    with pytest.raises(VariantNotFoundError):
        await use_case.execute(
            product_id=product.id,
            variant_id=other_product.variants[0].id,
            movement_type="restock",
            quantity_delta=5,
        )

    assert movements.recorded == []


async def test_soft_deleted_variant_absent_from_product_variants_raises_variant_not_found() -> (
    None
):
    # `get_by_id`'s LEFT JOIN already excludes soft-deleted variants from
    # `product.variants` -- a retired variant id is indistinguishable from a
    # foreign one at this layer, so the guard covers it for free.
    product_repository = InMemoryProductRepository()
    product = await make_persisted_product(product_repository, variants=[make_variant()])
    retired_variant_id = uuid4()  # never added -- simulates the read-time soft-delete filter
    use_case, movements = make_use_case(product_repository=product_repository)

    with pytest.raises(VariantNotFoundError):
        await use_case.execute(
            product_id=product.id,
            variant_id=retired_variant_id,
            movement_type="restock",
            quantity_delta=5,
        )

    assert movements.recorded == []


async def test_happy_path_delegates_arguments_verbatim_and_returns_the_stock_movement() -> None:
    product_repository = InMemoryProductRepository()
    variant = make_variant()
    product = await make_persisted_product(product_repository, variants=[variant])
    use_case, movements = make_use_case(product_repository=product_repository)

    result = await use_case.execute(
        product_id=product.id,
        variant_id=variant.id,
        movement_type="breakage",
        quantity_delta=-2,
        reason="Dropped during unboxing",
    )

    assert result.variant_id == variant.id
    assert result.movement_type == MovementType.BREAKAGE
    assert result.quantity_delta == -2
    assert result.reason == "Dropped during unboxing"
    assert movements.recorded == [result]
