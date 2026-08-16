"""Unit tests for `ListCatalogStockLevelsUseCase`.

Fakes only (`InMemoryProductRepository` + `InMemoryStockLevelReader`), same
convention as `test_list_variant_stock_movements.py`. Proves the three rules
that live in the use case (design.md's Interfaces/Contracts, verbatim
intent): the clamp (`max(0, below)`, never `max(1, ...)` -- D5/D11), the
AND-combined case-insensitive substring match on product name OR variant
color (D8/D9/D10), and the total ascending sort order with `variant_id` as
the final stable tiebreaker (design.md "Data Flow").
"""

from decimal import Decimal
from uuid import uuid4

from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.in_memory_product_repository import (
    InMemoryProductRepository,
)
from gcell.stock.application.list_catalog_stock_levels import (
    CatalogStockRow,
    ListCatalogStockLevelsUseCase,
)
from gcell.stock.domain.stock_movement import MovementType, StockMovement
from gcell.stock.infrastructure.in_memory_stock_level_reader import (
    InMemoryStockLevelReader,
)


def make_variant(color: str = "Negro") -> ProductVariant:
    return ProductVariant(
        id=uuid4(), color=color, price=Decimal("45000.00"), cost=Decimal("30000.00")
    )


def make_product(
    *, name: str = "Funda iPhone 15", variants: list[ProductVariant] | None = None
) -> Product:
    return Product(
        id=uuid4(),
        slug=f"funda-iphone-15-{uuid4().hex[:8]}",
        name=name,
        model=name,
        variants=variants if variants is not None else [make_variant()],
    )


def make_movement(variant_id, quantity_delta: int) -> StockMovement:
    return StockMovement(
        variant_id=variant_id,
        movement_type=MovementType.RESTOCK if quantity_delta >= 0 else MovementType.SALE,
        quantity_delta=quantity_delta,
        reason=None,
    )


async def make_use_case(
    *, products: list[Product], movements: list[StockMovement] | None = None
) -> ListCatalogStockLevelsUseCase:
    repository = InMemoryProductRepository()
    for product in products:
        await repository.add(product)
    reader = InMemoryStockLevelReader(movements or [])
    return ListCatalogStockLevelsUseCase(products=repository, stock_levels=reader)


async def test_empty_catalog_returns_empty_list() -> None:
    use_case = await make_use_case(products=[])

    rows = await use_case.execute()

    assert rows == []


async def test_below_none_returns_every_row_unfiltered() -> None:
    variant_a = make_variant("Negro")
    variant_b = make_variant("Blanco")
    product = make_product(variants=[variant_a, variant_b])
    use_case = await make_use_case(
        products=[product],
        movements=[make_movement(variant_a.id, 5), make_movement(variant_b.id, 2)],
    )

    rows = await use_case.execute(below=None)

    assert {row.variant_id for row in rows} == {variant_a.id, variant_b.id}


async def test_rows_are_sorted_ascending_by_quantity_with_stable_tiebreakers() -> None:
    variant_low = make_variant("Blanco")  # quantity 1
    variant_mid = make_variant("Negro")  # quantity 5
    variant_tie_a = make_variant("Rojo")  # quantity 3, "Alfa" product
    variant_tie_b = make_variant("Rojo")  # quantity 3, same color -> variant_id tiebreak
    product_low_mid = make_product(name="Zeta", variants=[variant_low, variant_mid])
    product_tie_a = make_product(name="Alfa", variants=[variant_tie_a])
    product_tie_b = make_product(name="Alfa", variants=[variant_tie_b])

    use_case = await make_use_case(
        products=[product_low_mid, product_tie_a, product_tie_b],
        movements=[
            make_movement(variant_low.id, 1),
            make_movement(variant_mid.id, 5),
            make_movement(variant_tie_a.id, 3),
            make_movement(variant_tie_b.id, 3),
        ],
    )

    rows = await use_case.execute()

    quantities = [row.quantity_on_hand for row in rows]
    assert quantities == sorted(quantities)
    assert quantities == [1, 3, 3, 5]
    # the two quantity-3 rows share product name + color -- variant_id is
    # the final tiebreaker, so the order must be deterministic (ascending
    # by str(variant_id)) rather than insertion order.
    tie_rows = [row for row in rows if row.quantity_on_hand == 3]
    expected_tie_order = sorted([variant_tie_a.id, variant_tie_b.id], key=str)
    assert [row.variant_id for row in tie_rows] == expected_tie_order


async def test_below_zero_returns_only_zero_quantity_rows() -> None:
    variant_zero = make_variant("Negro")
    variant_nonzero = make_variant("Blanco")
    product = make_product(variants=[variant_zero, variant_nonzero])
    use_case = await make_use_case(
        products=[product], movements=[make_movement(variant_nonzero.id, 4)]
    )

    rows = await use_case.execute(below=0)

    assert [row.variant_id for row in rows] == [variant_zero.id]
    assert rows[0].quantity_on_hand == 0


async def test_below_negative_clamps_to_zero_never_raises() -> None:
    variant_zero = make_variant("Negro")
    variant_nonzero = make_variant("Blanco")
    product = make_product(variants=[variant_zero, variant_nonzero])
    use_case = await make_use_case(
        products=[product], movements=[make_movement(variant_nonzero.id, 4)]
    )

    rows = await use_case.execute(below=-5)

    assert [row.variant_id for row in rows] == [variant_zero.id]


async def test_search_matches_product_name_case_insensitively() -> None:
    variant = make_variant("Negro")
    product = make_product(name="Funda Silicona", variants=[variant])
    use_case = await make_use_case(products=[product])

    rows = await use_case.execute(search="FUNDA")

    assert [row.variant_id for row in rows] == [variant.id]


async def test_search_matches_variant_color_case_insensitively() -> None:
    variant_match = make_variant("Negro")
    variant_other = make_variant("Blanco")
    product = make_product(variants=[variant_match, variant_other])
    use_case = await make_use_case(products=[product])

    rows = await use_case.execute(search="negro")

    assert [row.variant_id for row in rows] == [variant_match.id]


async def test_blank_or_whitespace_search_is_ignored() -> None:
    variant = make_variant()
    product = make_product(variants=[variant])
    use_case = await make_use_case(products=[product])

    rows = await use_case.execute(search="   ")

    assert [row.variant_id for row in rows] == [variant.id]


async def test_below_and_search_combine_with_and() -> None:
    variant_match_both = make_variant("Negro")  # quantity 0, product name matches
    variant_match_search_only = make_variant("Negro")  # quantity 4, product name matches
    variant_match_below_only = make_variant("Negro")  # quantity 0, product name does not match
    product_matching_search = make_product(
        name="Funda Silicona", variants=[variant_match_both, variant_match_search_only]
    )
    product_not_matching_search = make_product(
        name="Cargador Rapido", variants=[variant_match_below_only]
    )
    use_case = await make_use_case(
        products=[product_matching_search, product_not_matching_search],
        movements=[make_movement(variant_match_search_only.id, 4)],
    )

    rows = await use_case.execute(below=0, search="funda")

    assert [row.variant_id for row in rows] == [variant_match_both.id]


async def test_search_with_sql_injection_shaped_string_returns_empty_list_safely() -> None:
    variant = make_variant()
    product = make_product(variants=[variant])
    use_case = await make_use_case(products=[product])

    rows = await use_case.execute(search="'; DROP TABLE products;--")

    assert rows == []


def test_catalog_stock_row_carries_expected_fields() -> None:
    product_id = uuid4()
    variant_id = uuid4()
    row = CatalogStockRow(
        product_id=product_id,
        product_slug="funda-iphone-15",
        product_name="Funda iPhone 15",
        product_model="Funda iPhone 15",
        variant_id=variant_id,
        color="Negro",
        quantity_on_hand=3,
    )

    assert row.product_id == product_id
    assert row.variant_id == variant_id
    assert row.quantity_on_hand == 3
