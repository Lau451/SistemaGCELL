"""Integration tests for `PostgresProductRepository` against real local Postgres.

Uses `db_conn` (per-test rollback isolation, see `tests/conftest.py`).
`Product`/`ProductVariant` equality is id-based (see design.md "identity,
equality, and money invariants"), so `read_back == written` is trivially
true on `id` alone -- assertions here compare fields (`slug`, `name`,
`model`, `color`, `price`, `cost`) explicitly, not just `==`.
"""

from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest

from gcell.products.application.exceptions import DuplicateProductSlugError
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)


def make_product(**overrides: object) -> Product:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "slug": f"iphone-13-funda-{uuid4().hex[:8]}",
        "name": "Funda transparente",
        "model": "iPhone 13",
        "variants": [
            ProductVariant(
                id=uuid4(),
                color="Negro",
                price=Decimal("45000.00"),
                cost=Decimal("30000.00"),
            )
        ],
    }
    defaults.update(overrides)
    return Product(**defaults)  # type: ignore[arg-type]


async def test_add_then_get_by_slug_round_trips_fields(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    product = make_product()

    await repository.add(product)
    fetched = await repository.get_by_slug(product.slug)

    assert fetched is not None
    assert fetched.id == product.id
    assert fetched.slug == product.slug
    assert fetched.name == product.name
    assert fetched.model == product.model
    assert len(fetched.variants) == 1
    fetched_variant = fetched.variants[0]
    original_variant = product.variants[0]
    assert fetched_variant.id == original_variant.id
    assert fetched_variant.color == original_variant.color
    assert fetched_variant.price == original_variant.price
    assert fetched_variant.cost == original_variant.cost


async def test_add_then_get_by_id_round_trips_fields(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    product = make_product()

    await repository.add(product)
    fetched = await repository.get_by_id(product.id)

    assert fetched is not None
    assert fetched.id == product.id
    assert fetched.slug == product.slug


async def test_price_and_cost_survive_round_trip_at_scale_two(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    product = make_product(
        variants=[
            ProductVariant(
                id=uuid4(), color="Negro", price=Decimal("45000"), cost=Decimal("30000.5")
            )
        ]
    )

    await repository.add(product)
    fetched = await repository.get_by_slug(product.slug)

    assert fetched is not None
    variant = fetched.variants[0]
    assert variant.price == Decimal("45000.00")
    assert variant.cost == Decimal("30000.50")
    assert isinstance(variant.price, Decimal)
    assert isinstance(variant.cost, Decimal)


async def test_zero_variant_product_reads_back_with_empty_variants(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    product = make_product(variants=[])

    await repository.add(product)
    fetched = await repository.get_by_slug(product.slug)

    assert fetched is not None
    assert fetched.variants == []


async def test_get_by_slug_returns_none_for_unknown_slug(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)

    assert await repository.get_by_slug("no-existe-de-verdad") is None


async def test_get_by_id_returns_none_for_unknown_id(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)

    assert await repository.get_by_id(uuid4()) is None


async def test_duplicate_slug_raises_duplicate_product_slug_error(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    slug = f"duplicado-{uuid4().hex[:8]}"
    await repository.add(make_product(slug=slug))

    with pytest.raises(DuplicateProductSlugError):
        await repository.add(make_product(slug=slug, name="Otra funda"))


async def test_duplicate_slug_leaves_no_new_product_row(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    slug = f"duplicado-sin-fuga-{uuid4().hex[:8]}"
    first = make_product(slug=slug)
    await repository.add(first)

    with pytest.raises(DuplicateProductSlugError):
        await repository.add(make_product(slug=slug, name="Otra funda"))

    row_count = await db_conn.fetchval(
        "SELECT count(*) FROM products WHERE slug = $1", slug
    )
    assert row_count == 1


async def test_failed_variant_insert_leaves_no_partial_rows(db_conn) -> None:
    """A constraint violation on the second variant must roll back the whole
    add() -- neither the product row nor the first variant row survive.
    """
    repository = PostgresProductRepository(db_conn)
    clashing_id = uuid4()
    product = make_product(
        variants=[
            ProductVariant(
                id=clashing_id, color="Negro", price=Decimal("100.00"), cost=Decimal("50.00")
            ),
            ProductVariant(
                # Same id as the first variant -- violates the primary key,
                # forcing a mid-transaction failure that isn't already
                # rejected by the domain's own validation.
                id=clashing_id,
                color="Rojo",
                price=Decimal("120.00"),
                cost=Decimal("60.00"),
            ),
        ]
    )

    with pytest.raises(asyncpg.PostgresError):
        await repository.add(product)

    product_row_count = await db_conn.fetchval(
        "SELECT count(*) FROM products WHERE id = $1", product.id
    )
    variant_row_count = await db_conn.fetchval(
        "SELECT count(*) FROM product_variants WHERE product_id = $1", product.id
    )
    assert product_row_count == 0
    assert variant_row_count == 0


async def test_list_all_includes_products_with_and_without_variants(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    with_variant = make_product()
    without_variant = make_product(variants=[])
    await repository.add(with_variant)
    await repository.add(without_variant)

    all_products = await repository.list_all()
    ids = {product.id for product in all_products}

    assert with_variant.id in ids
    assert without_variant.id in ids
    fetched_without = next(p for p in all_products if p.id == without_variant.id)
    assert fetched_without.variants == []


async def test_list_all_keeps_product_with_every_variant_retired(db_conn) -> None:
    """The ON-vs-WHERE trap (design.md "the LEFT JOIN filter goes in ON,
    never in WHERE"). Retiring every variant of a product via raw SQL (no
    port method exists yet -- that is PR2's job) must NOT remove the product
    from list_all(): the variant filter belongs in the LEFT JOIN's ON
    clause, not in a WHERE that would silently degrade the join to an INNER
    JOIN and drop products with zero active variants.
    """
    repository = PostgresProductRepository(db_conn)
    product = make_product()
    await repository.add(product)

    await db_conn.execute(
        "UPDATE product_variants SET deleted_at = now() WHERE product_id = $1",
        product.id,
    )

    all_products = await repository.list_all()
    fetched = next((p for p in all_products if p.id == product.id), None)

    assert fetched is not None
    assert fetched.variants == []
