"""Unit tests for `CreateStockedProductUseCase` -- slug derivation (mirrors
`CreateProductUseCase`) plus the ">0 seed quantity -> exactly one `restock`
movement" rule, delegated to `RegisterStockedProductUseCase`.

See design.md Decisions 1-2: the use case filters seed quantities to only
the `>0` entries and relies on `StockMovement.__post_init__`'s non-zero
invariant as a backstop only, never as the mechanism.
"""

from decimal import Decimal
from uuid import uuid4

from gcell.products.domain.product import ProductVariant
from gcell.products.infrastructure.in_memory_product_repository import (
    InMemoryProductRepository,
)
from gcell.stock.domain.stock_movement import MovementType
from gcell.stock.infrastructure.in_memory_stock_movement_repository import (
    InMemoryStockMovementRepository,
)


def make_variant(color: str = "Negro") -> ProductVariant:
    return ProductVariant(
        id=uuid4(), color=color, price=Decimal("45000.00"), cost=Decimal("30000.00")
    )


async def test_execute_derives_a_slug_from_the_name() -> None:
    from gcell.stock.application.create_stocked_product import (
        CreateStockedProductUseCase,
    )

    products = InMemoryProductRepository()
    movements = InMemoryStockMovementRepository()
    use_case = CreateStockedProductUseCase(products=products, movements=movements)

    product = await use_case.execute(
        name="iPhone 15", model="iPhone 15", variants=[make_variant()]
    )

    assert product.slug == "iphone-15"
    assert product.name == "iPhone 15"


async def test_execute_persists_the_product_through_the_repository() -> None:
    from gcell.stock.application.create_stocked_product import (
        CreateStockedProductUseCase,
    )

    products = InMemoryProductRepository()
    movements = InMemoryStockMovementRepository()
    use_case = CreateStockedProductUseCase(products=products, movements=movements)

    product = await use_case.execute(
        name="iPhone 15", model="iPhone 15", variants=[make_variant()]
    )

    assert await products.get_by_id(product.id) == product
    assert await products.get_by_slug("iphone-15") == product


async def test_variant_with_positive_initial_quantity_records_one_restock_movement() -> None:
    from gcell.stock.application.create_stocked_product import (
        CreateStockedProductUseCase,
    )

    products = InMemoryProductRepository()
    movements = InMemoryStockMovementRepository()
    use_case = CreateStockedProductUseCase(products=products, movements=movements)
    variant = make_variant()

    await use_case.execute(
        name="iPhone 15",
        model="iPhone 15",
        variants=[variant],
        initial_quantities={variant.id: 5},
    )

    assert len(movements.recorded) == 1
    recorded = movements.recorded[0]
    assert recorded.variant_id == variant.id
    assert recorded.movement_type == MovementType.RESTOCK
    assert recorded.quantity_delta == 5


async def test_zero_or_absent_initial_quantity_records_no_movement() -> None:
    from gcell.stock.application.create_stocked_product import (
        CreateStockedProductUseCase,
    )

    products = InMemoryProductRepository()
    movements = InMemoryStockMovementRepository()
    use_case = CreateStockedProductUseCase(products=products, movements=movements)
    zero_variant = make_variant("Rojo")
    absent_variant = make_variant("Azul")

    await use_case.execute(
        name="iPhone 15",
        model="iPhone 15",
        variants=[zero_variant, absent_variant],
        initial_quantities={zero_variant.id: 0},
    )

    assert movements.recorded == []


async def test_mixed_variants_only_seed_the_positive_ones() -> None:
    from gcell.stock.application.create_stocked_product import (
        CreateStockedProductUseCase,
    )

    products = InMemoryProductRepository()
    movements = InMemoryStockMovementRepository()
    use_case = CreateStockedProductUseCase(products=products, movements=movements)
    seeded = make_variant("Negro")
    unseeded_zero = make_variant("Rojo")
    unseeded_absent = make_variant("Azul")

    await use_case.execute(
        name="iPhone 15",
        model="iPhone 15",
        variants=[seeded, unseeded_zero, unseeded_absent],
        initial_quantities={seeded.id: 3, unseeded_zero.id: 0},
    )

    assert len(movements.recorded) == 1
    assert movements.recorded[0].variant_id == seeded.id
    assert movements.recorded[0].quantity_delta == 3


async def test_no_initial_quantities_argument_records_no_movement() -> None:
    from gcell.stock.application.create_stocked_product import (
        CreateStockedProductUseCase,
    )

    products = InMemoryProductRepository()
    movements = InMemoryStockMovementRepository()
    use_case = CreateStockedProductUseCase(products=products, movements=movements)

    await use_case.execute(
        name="iPhone 15", model="iPhone 15", variants=[make_variant()]
    )

    assert movements.recorded == []
