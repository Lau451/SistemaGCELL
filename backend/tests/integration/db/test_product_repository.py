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

from gcell.products.application.exceptions import (
    DuplicateProductSlugError,
    ProductNotFoundError,
    VariantNotFoundError,
)
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)
from gcell.stock.domain.stock_movement import MovementType, StockMovement
from gcell.stock.infrastructure.postgres_stock_movement_repository import (
    PostgresStockMovementRepository,
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


async def test_update_persists_name_and_model_but_never_slug(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    product = make_product()
    await repository.add(product)

    await repository.update(
        Product(
            id=product.id,
            slug=product.slug,
            name="Nuevo nombre",
            model="Nuevo modelo",
            variants=[],
        )
    )

    fetched = await repository.get_by_id(product.id)
    assert fetched is not None
    assert fetched.name == "Nuevo nombre"
    assert fetched.model == "Nuevo modelo"
    assert fetched.slug == product.slug


async def test_update_upserts_a_new_and_an_existing_variant_in_one_call(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    product = make_product()
    await repository.add(product)
    existing_variant = product.variants[0]
    new_variant = ProductVariant(
        id=uuid4(), color="Rojo", price=Decimal("47000.00"), cost=Decimal("31000.00")
    )
    edited_existing = ProductVariant(
        id=existing_variant.id,
        color="Negro Mate",
        price=Decimal("46000.00"),
        cost=Decimal("30500.00"),
    )

    await repository.update(
        Product(
            id=product.id,
            slug=product.slug,
            name=product.name,
            model=product.model,
            variants=[edited_existing, new_variant],
        )
    )

    fetched = await repository.get_by_id(product.id)
    assert fetched is not None
    variants_by_id = {variant.id: variant for variant in fetched.variants}
    assert variants_by_id[existing_variant.id].color == "Negro Mate"
    assert variants_by_id[new_variant.id].color == "Rojo"


async def test_update_on_a_retired_product_raises_product_not_found(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    product = make_product()
    await repository.add(product)
    await repository.soft_delete(product.id)

    with pytest.raises(ProductNotFoundError):
        await repository.update(
            Product(
                id=product.id,
                slug=product.slug,
                name="X",
                model="X",
                variants=[],
            )
        )


async def test_update_on_an_unknown_product_raises_product_not_found(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    unknown_id = uuid4()

    with pytest.raises(ProductNotFoundError):
        await repository.update(
            Product(id=unknown_id, slug="ghost", name="X", model="X", variants=[])
        )


async def test_update_mid_transaction_failure_leaves_nothing_changed(db_conn) -> None:
    """A constraint violation on the second variant must roll back the
    WHOLE update() -- neither the field edit nor the first variant's
    upsert survive (design.md "A failed update leaves no partial change").

    The `ON CONFLICT (id) DO UPDATE` upsert means a duplicate id within the
    SAME call is absorbed silently (not an error, by design) -- so this
    forces a REAL DB-only constraint the domain does not itself check:
    `numeric(10, 2)` magnitude overflow (the domain validates finiteness,
    non-negativity, and decimal-place count, but not column precision).
    """
    repository = PostgresProductRepository(db_conn)
    product = make_product()
    await repository.add(product)
    first_variant_id = uuid4()
    overflowing_variant_id = uuid4()

    with pytest.raises(asyncpg.PostgresError):
        await repository.update(
            Product(
                id=product.id,
                slug=product.slug,
                name="Debe no persistir",
                model="Debe no persistir",
                variants=[
                    ProductVariant(
                        id=first_variant_id,
                        color="Verde",
                        price=Decimal("1.00"),
                        cost=Decimal("1.00"),
                    ),
                    ProductVariant(
                        id=overflowing_variant_id,
                        color="Amarillo",
                        price=Decimal("999999999.99"),  # exceeds numeric(10,2)
                        cost=Decimal("2.00"),
                    ),
                ],
            )
        )

    fetched = await repository.get_by_id(product.id)
    assert fetched is not None
    assert fetched.name == product.name
    assert fetched.model == product.model
    first_variant_row = await db_conn.fetchrow(
        "SELECT 1 FROM product_variants WHERE id = $1", first_variant_id
    )
    assert first_variant_row is None


async def test_soft_delete_retires_the_product_via_update(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    product = make_product()
    await repository.add(product)

    await repository.soft_delete(product.id)

    assert await repository.get_by_id(product.id) is None
    row = await db_conn.fetchrow(
        "SELECT deleted_at FROM products WHERE id = $1", product.id
    )
    assert row is not None
    assert row["deleted_at"] is not None

    # sdd-verify WARNING (re-verify pass): the spec's "neither variant row's
    # deleted_at MUST change" sub-claim had no dedicated runtime assertion --
    # cascade is a read-time join filter, never a second write against
    # product_variants (design.md "cascades at read time, not by stamping
    # variants").
    variant_row = await db_conn.fetchrow(
        "SELECT deleted_at FROM product_variants WHERE product_id = $1",
        product.id,
    )
    assert variant_row is not None
    assert variant_row["deleted_at"] is None


async def test_soft_delete_on_an_unknown_product_raises_product_not_found(
    db_conn,
) -> None:
    repository = PostgresProductRepository(db_conn)

    with pytest.raises(ProductNotFoundError):
        await repository.soft_delete(uuid4())


async def test_soft_delete_on_an_already_retired_product_raises_product_not_found(
    db_conn,
) -> None:
    repository = PostgresProductRepository(db_conn)
    product = make_product()
    await repository.add(product)
    await repository.soft_delete(product.id)

    with pytest.raises(ProductNotFoundError):
        await repository.soft_delete(product.id)


async def test_soft_delete_variant_retires_only_that_variant(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    variant_a = ProductVariant(
        id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
    )
    variant_b = ProductVariant(
        id=uuid4(), color="Rojo", price=Decimal("47000.00"), cost=Decimal("31000.00")
    )
    product = make_product(variants=[variant_a, variant_b])
    await repository.add(product)

    await repository.soft_delete_variant(product.id, variant_a.id)

    fetched = await repository.get_by_id(product.id)
    assert fetched is not None
    variant_ids = {variant.id for variant in fetched.variants}
    assert variant_a.id not in variant_ids
    assert variant_b.id in variant_ids


async def test_soft_delete_variant_of_a_different_product_raises_variant_not_found(
    db_conn,
) -> None:
    """IDOR guard: `DELETE .../{A}/variants/{v_of_B}` must never succeed
    and never confirm the variant's existence -- both surface as the same
    `VariantNotFoundError` at this layer.
    """
    repository = PostgresProductRepository(db_conn)
    product_a = make_product()
    product_b = make_product()
    await repository.add(product_a)
    await repository.add(product_b)

    with pytest.raises(VariantNotFoundError):
        await repository.soft_delete_variant(product_a.id, product_b.variants[0].id)


async def test_soft_delete_variant_already_retired_raises_variant_not_found(
    db_conn,
) -> None:
    repository = PostgresProductRepository(db_conn)
    product = make_product()
    await repository.add(product)
    variant_id = product.variants[0].id
    await repository.soft_delete_variant(product.id, variant_id)

    with pytest.raises(VariantNotFoundError):
        await repository.soft_delete_variant(product.id, variant_id)


async def test_slug_exists_is_true_for_a_live_slug(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)
    product = make_product()
    await repository.add(product)

    assert await repository.slug_exists(product.slug) is True


async def test_slug_exists_is_false_for_an_unknown_slug(db_conn) -> None:
    repository = PostgresProductRepository(db_conn)

    assert await repository.slug_exists("no-existe-de-verdad") is False


async def test_slug_exists_is_true_for_a_retired_products_slug(db_conn) -> None:
    """design.md "retired slugs stay reserved" -- `slug_exists` ignores
    `deleted_at` on purpose, mirroring the global unique index.
    """
    repository = PostgresProductRepository(db_conn)
    product = make_product()
    await repository.add(product)
    await repository.soft_delete(product.id)

    assert await repository.slug_exists(product.slug) is True


async def test_update_upsert_never_clears_deleted_at_on_a_retired_variant(
    db_conn,
) -> None:
    """The `ON CONFLICT (id) DO UPDATE SET color=,price=,cost=` clause must
    never include `deleted_at` -- a replayed/retried update() body must not
    be able to resurrect a retired variant.
    """
    repository = PostgresProductRepository(db_conn)
    product = make_product()
    await repository.add(product)
    variant_id = product.variants[0].id
    await repository.soft_delete_variant(product.id, variant_id)

    replayed_variant = ProductVariant(
        id=variant_id, color="Negro", price=Decimal("99999.00"), cost=Decimal("1.00")
    )
    await repository.update(
        Product(
            id=product.id,
            slug=product.slug,
            name=product.name,
            model=product.model,
            variants=[replayed_variant],
        )
    )

    row = await db_conn.fetchrow(
        "SELECT deleted_at, price FROM product_variants WHERE id = $1", variant_id
    )
    assert row is not None
    assert row["deleted_at"] is not None
    fetched = await repository.get_by_id(product.id)
    assert fetched is not None
    assert all(variant.id != variant_id for variant in fetched.variants)


async def test_retiring_a_product_leaves_its_stock_movements_ledger_untouched(
    db_conn,
) -> None:
    """The headline success criterion: no code path may `UPDATE`/`DELETE`
    `stock_movements`. Retiring a product whose variant has real ledger
    rows must succeed, and count(*)/sum(quantity_delta) must be provably
    unchanged.
    """
    product_repository = PostgresProductRepository(db_conn)
    movement_repository = PostgresStockMovementRepository(db_conn)
    product = make_product()
    await product_repository.add(product)
    variant_id = product.variants[0].id
    await movement_repository.record(
        StockMovement(
            variant_id=variant_id, movement_type=MovementType.RESTOCK, quantity_delta=10
        )
    )
    await movement_repository.record(
        StockMovement(
            variant_id=variant_id, movement_type=MovementType.SALE, quantity_delta=-3
        )
    )
    before_count = await db_conn.fetchval(
        "SELECT count(*) FROM stock_movements WHERE variant_id = $1", variant_id
    )
    before_sum = await db_conn.fetchval(
        "SELECT sum(quantity_delta) FROM stock_movements WHERE variant_id = $1",
        variant_id,
    )

    await product_repository.soft_delete(product.id)

    after_count = await db_conn.fetchval(
        "SELECT count(*) FROM stock_movements WHERE variant_id = $1", variant_id
    )
    after_sum = await db_conn.fetchval(
        "SELECT sum(quantity_delta) FROM stock_movements WHERE variant_id = $1",
        variant_id,
    )
    assert after_count == before_count == 2
    assert after_sum == before_sum == 7


async def test_retiring_a_single_variant_leaves_its_stock_movements_ledger_untouched(
    db_conn,
) -> None:
    product_repository = PostgresProductRepository(db_conn)
    movement_repository = PostgresStockMovementRepository(db_conn)
    product = make_product()
    await product_repository.add(product)
    variant_id = product.variants[0].id
    await movement_repository.record(
        StockMovement(
            variant_id=variant_id, movement_type=MovementType.RESTOCK, quantity_delta=5
        )
    )

    await product_repository.soft_delete_variant(product.id, variant_id)

    row_count = await db_conn.fetchval(
        "SELECT count(*) FROM stock_movements WHERE variant_id = $1", variant_id
    )
    total = await db_conn.fetchval(
        "SELECT sum(quantity_delta) FROM stock_movements WHERE variant_id = $1",
        variant_id,
    )
    assert row_count == 1
    assert total == 5
