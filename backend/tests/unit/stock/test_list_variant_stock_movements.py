"""Unit tests for `ListVariantStockMovementsUseCase`.

Fakes/spies only (`InMemoryProductRepository` + a spying
`InMemoryStockMovementHistoryReader`), same convention as
`test_record_variant_stock_movement.py`. Proves the ownership (IDOR) guard
runs BEFORE `history_reader.list_for_variant` is ever called -- an unknown
product and a variant owned by another product must both raise before any
read (spec: stock-movement-recording "List Variant Stock Movements Use
Case"); the limit-clamp table (design.md Decision 3); the `limit+1` trim
so `next_before_id` is `None` only at the true end (spec: "Cursor
pagination returns strictly older rows with no gaps or duplicates"); and
that an empty variant returns `[]` with `next_before_id: None`.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from gcell.products.application.exceptions import ProductNotFoundError, VariantNotFoundError
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.in_memory_product_repository import (
    InMemoryProductRepository,
)
from gcell.stock.application.list_variant_stock_movements import (
    ListVariantStockMovementsUseCase,
)
from gcell.stock.application.stock_movement_history_reader import RecordedStockMovement
from gcell.stock.domain.stock_movement import MovementType
from gcell.stock.infrastructure.in_memory_stock_movement_history_reader import (
    InMemoryStockMovementHistoryReader,
)


class _SpyingHistoryReader(InMemoryStockMovementHistoryReader):
    def __init__(self, movements: list[RecordedStockMovement]) -> None:
        super().__init__(movements)
        self.calls: list[tuple] = []

    async def list_for_variant(self, variant_id, limit, before_id):
        self.calls.append((variant_id, limit, before_id))
        return await super().list_for_variant(variant_id, limit, before_id)


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


def make_movement(variant_id, movement_id: int) -> RecordedStockMovement:
    return RecordedStockMovement(
        id=movement_id,
        variant_id=variant_id,
        movement_type=MovementType.RESTOCK,
        quantity_delta=1,
        reason=None,
        created_at=datetime(2026, 1, movement_id % 28 + 1, tzinfo=UTC),
    )


def make_use_case(
    *,
    product_repository: InMemoryProductRepository | None = None,
    history_reader: _SpyingHistoryReader | None = None,
):
    reader = history_reader if history_reader is not None else _SpyingHistoryReader([])
    use_case = ListVariantStockMovementsUseCase(
        products=product_repository or InMemoryProductRepository(),
        history_reader=reader,
    )
    return use_case, reader


async def test_unknown_product_raises_product_not_found_before_any_reader_call() -> None:
    use_case, reader = make_use_case()

    with pytest.raises(ProductNotFoundError):
        await use_case.execute(product_id=uuid4(), variant_id=uuid4())

    assert reader.calls == []


async def test_variant_owned_by_another_product_raises_variant_not_found_before_read() -> None:
    product_repository = InMemoryProductRepository()
    product = await make_persisted_product(product_repository)
    other_product = await make_persisted_product(product_repository)
    use_case, reader = make_use_case(product_repository=product_repository)

    with pytest.raises(VariantNotFoundError):
        await use_case.execute(
            product_id=product.id, variant_id=other_product.variants[0].id
        )

    assert reader.calls == []


@pytest.mark.parametrize(
    ("requested_limit", "expected_effective_limit"),
    [
        pytest.param(0, 1, id="zero-clamps-to-one"),
        pytest.param(500, 100, id="above-cap-clamps-to-cap"),
        pytest.param(None, 20, id="omitted-defaults-to-twenty"),
    ],
)
async def test_limit_is_clamped_and_requested_as_limit_plus_one(
    requested_limit: int | None, expected_effective_limit: int
) -> None:
    product_repository = InMemoryProductRepository()
    variant = make_variant()
    product = await make_persisted_product(product_repository, variants=[variant])
    use_case, reader = make_use_case(product_repository=product_repository)

    kwargs = {} if requested_limit is None else {"limit": requested_limit}
    await use_case.execute(product_id=product.id, variant_id=variant.id, **kwargs)

    assert reader.calls == [(variant.id, expected_effective_limit + 1, None)]


async def test_exactly_limit_movements_yields_no_next_cursor() -> None:
    product_repository = InMemoryProductRepository()
    variant = make_variant()
    product = await make_persisted_product(product_repository, variants=[variant])
    movements = [make_movement(variant.id, i) for i in range(1, 3)]  # ids 1, 2
    use_case, reader = make_use_case(
        product_repository=product_repository, history_reader=_SpyingHistoryReader(movements)
    )

    page = await use_case.execute(product_id=product.id, variant_id=variant.id, limit=2)

    assert [item.id for item in page.items] == [2, 1]
    assert page.next_before_id is None


async def test_more_than_limit_movements_yields_next_cursor_and_trims_the_extra_row() -> None:
    product_repository = InMemoryProductRepository()
    variant = make_variant()
    product = await make_persisted_product(product_repository, variants=[variant])
    movements = [make_movement(variant.id, i) for i in range(1, 4)]  # ids 1, 2, 3
    use_case, reader = make_use_case(
        product_repository=product_repository, history_reader=_SpyingHistoryReader(movements)
    )

    page = await use_case.execute(product_id=product.id, variant_id=variant.id, limit=2)

    assert [item.id for item in page.items] == [3, 2]
    assert page.next_before_id == 2


async def test_variant_with_no_movements_returns_empty_list_and_no_cursor() -> None:
    product_repository = InMemoryProductRepository()
    variant = make_variant()
    product = await make_persisted_product(product_repository, variants=[variant])
    use_case, reader = make_use_case(product_repository=product_repository)

    page = await use_case.execute(product_id=product.id, variant_id=variant.id)

    assert page.items == []
    assert page.next_before_id is None
