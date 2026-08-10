"""Unit tests for `RegisterStockedProductUseCase`.

Orchestrates `ProductRepository` + `StockMovementRepository` as plain ports
-- no transaction handling here, that is caller-owned (composition root),
per design.md "transaction boundary at the composition root, orchestration
in a use case". Lives in `stock/application/` (legal direction
stock -> products), imports from `gcell.products.*` for the port and entity
types only.
"""

from decimal import Decimal
from uuid import uuid4

from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.in_memory_product_repository import (
    InMemoryProductRepository,
)
from gcell.stock.application.register_stocked_product import (
    RegisterStockedProductUseCase,
)
from gcell.stock.domain.stock_movement import MovementType, StockMovement
from gcell.stock.infrastructure.in_memory_stock_movement_repository import (
    InMemoryStockMovementRepository,
)


def make_product(**overrides: object) -> Product:
    variant_id = uuid4()
    defaults: dict[str, object] = {
        "id": uuid4(),
        "slug": f"iphone-13-funda-{uuid4().hex[:8]}",
        "name": "Funda transparente",
        "model": "iPhone 13",
        "variants": [
            ProductVariant(
                id=variant_id,
                color="Negro",
                price=Decimal("45000.00"),
                cost=Decimal("30000.00"),
            )
        ],
    }
    defaults.update(overrides)
    return Product(**defaults)  # type: ignore[arg-type]


async def test_zero_stock_registration_succeeds_with_no_movements_recorded() -> None:
    products = InMemoryProductRepository()
    movements = InMemoryStockMovementRepository()
    use_case = RegisterStockedProductUseCase(products=products, movements=movements)
    product = make_product()

    result = await use_case.execute(product)

    assert await products.get_by_id(result.id) == result
    assert movements.recorded == []


async def test_registration_with_initial_movement_records_it_against_the_repository() -> None:
    products = InMemoryProductRepository()
    movements = InMemoryStockMovementRepository()
    use_case = RegisterStockedProductUseCase(products=products, movements=movements)
    product = make_product()
    variant_id = product.variants[0].id
    initial_movement = StockMovement(
        variant_id=variant_id,
        movement_type=MovementType.RESTOCK,
        quantity_delta=15,
    )

    await use_case.execute(product, initial_movements=[initial_movement])

    assert movements.recorded == [initial_movement]
    assert await products.get_by_id(product.id) == product


async def test_registration_with_multiple_initial_movements_records_all() -> None:
    products = InMemoryProductRepository()
    movements = InMemoryStockMovementRepository()
    use_case = RegisterStockedProductUseCase(products=products, movements=movements)
    product = make_product()
    variant_id = product.variants[0].id
    first = StockMovement(
        variant_id=variant_id, movement_type=MovementType.RESTOCK, quantity_delta=15
    )
    second = StockMovement(
        variant_id=variant_id, movement_type=MovementType.ADJUSTMENT, quantity_delta=-2
    )

    await use_case.execute(product, initial_movements=[first, second])

    assert movements.recorded == [first, second]
