"""Integration tests for `PostgresProductImageRepository` against real local
Postgres.

Uses `db_conn` (per-test rollback isolation, see `tests/conftest.py`).
`product_images` already exists (migration `20260810000449_products_
catalog.sql`) — this PR adds no migration, only port+adapter code (see
proposal.md decision 2).
"""

from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest

from gcell.products.application.exceptions import ImageNotFoundError
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.domain.product_image import ProductImage
from gcell.products.infrastructure.postgres_product_image_repository import (
    PostgresProductImageRepository,
)
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)


def make_product(**overrides: object) -> Product:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "slug": f"funda-imagenes-{uuid4().hex[:8]}",
        "name": "Funda con imagenes",
        "model": "iPhone 13",
        "variants": [
            ProductVariant(
                id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
            )
        ],
    }
    defaults.update(overrides)
    return Product(**defaults)  # type: ignore[arg-type]


def make_image(**overrides: object) -> ProductImage:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "product_id": uuid4(),
        "variant_id": None,
        "storage_path": f"funda/hero-{uuid4().hex[:12]}.webp",
        "alt_text": None,
        "sort_order": 0,
    }
    defaults.update(overrides)
    return ProductImage(**defaults)  # type: ignore[arg-type]


async def test_add_hero_image_persists_with_null_variant_id(db_conn) -> None:
    """spec: admin-product-images "Hero Assignment Uses A Null Variant Id"."""
    product_repository = PostgresProductRepository(db_conn)
    image_repository = PostgresProductImageRepository(db_conn)
    product = make_product()
    await product_repository.add(product)
    image = make_image(product_id=product.id, variant_id=None)

    await image_repository.add(image)
    fetched = await image_repository.get_by_id(image.id)

    assert fetched is not None
    assert fetched.variant_id is None
    assert fetched.product_id == product.id
    assert fetched.storage_path == image.storage_path


async def test_add_image_with_variant_from_a_different_product_raises_fk_violation(
    db_conn,
) -> None:
    """The composite FK `product_images_variant_fk` MATCH SIMPLE rejects a
    (product_id, variant_id) pair spanning two different products -- the
    image must reference a variant that actually belongs to the stated
    product.
    """
    product_repository = PostgresProductRepository(db_conn)
    image_repository = PostgresProductImageRepository(db_conn)
    product_a = make_product()
    product_b = make_product()
    await product_repository.add(product_a)
    await product_repository.add(product_b)
    foreign_variant_id = product_b.variants[0].id
    image = make_image(product_id=product_a.id, variant_id=foreign_variant_id)

    with pytest.raises(asyncpg.ForeignKeyViolationError):
        await image_repository.add(image)

    row_count = await db_conn.fetchval(
        "SELECT count(*) FROM product_images WHERE id = $1", image.id
    )
    assert row_count == 0


async def test_list_for_product_hides_images_of_a_soft_deleted_variant(
    db_conn,
) -> None:
    """spec: product-persistence "Images Of A Soft-Deleted Variant Are
    Hidden At Read Time" -- retiring a variant hides its images from the
    product's image list, but the rows themselves must still exist
    unchanged (no purge).
    """
    variant_a = ProductVariant(
        id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
    )
    variant_b = ProductVariant(
        id=uuid4(), color="Rojo", price=Decimal("47000.00"), cost=Decimal("31000.00")
    )
    product = make_product(variants=[variant_a, variant_b])
    product_repository = PostgresProductRepository(db_conn)
    image_repository = PostgresProductImageRepository(db_conn)
    await product_repository.add(product)
    image_a1 = make_image(product_id=product.id, variant_id=variant_a.id, sort_order=0)
    image_a2 = make_image(product_id=product.id, variant_id=variant_a.id, sort_order=1)
    image_b1 = make_image(product_id=product.id, variant_id=variant_b.id, sort_order=0)
    await image_repository.add(image_a1)
    await image_repository.add(image_a2)
    await image_repository.add(image_b1)

    await product_repository.soft_delete_variant(product.id, variant_a.id)
    listed = await image_repository.list_for_product(product.id)

    assert {image.id for image in listed} == {image_b1.id}
    # Retired variant's image rows must still exist unchanged -- no purge.
    surviving_rows = await db_conn.fetchval(
        "SELECT count(*) FROM product_images WHERE variant_id = $1", variant_a.id
    )
    assert surviving_rows == 2


async def test_list_for_product_includes_hero_images_regardless_of_variant_state(
    db_conn,
) -> None:
    """spec: product-persistence, companion scenario to the above -- a
    hero image (`variant_id IS NULL`) must never be hidden by any
    variant's retirement.
    """
    variant = ProductVariant(
        id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
    )
    product = make_product(variants=[variant])
    product_repository = PostgresProductRepository(db_conn)
    image_repository = PostgresProductImageRepository(db_conn)
    await product_repository.add(product)
    hero_image = make_image(product_id=product.id, variant_id=None, sort_order=0)
    variant_image = make_image(product_id=product.id, variant_id=variant.id, sort_order=0)
    await image_repository.add(hero_image)
    await image_repository.add(variant_image)

    await product_repository.soft_delete_variant(product.id, variant.id)
    listed = await image_repository.list_for_product(product.id)

    assert {image.id for image in listed} == {hero_image.id}


async def test_reorder_writes_sequential_sort_order_atomically(db_conn) -> None:
    """spec: product-persistence "adapters agree on image operations" --
    `reorder` writes `sort_order` 0..n-1 matching the given list's
    position, in one transaction.
    """
    product = make_product()
    product_repository = PostgresProductRepository(db_conn)
    image_repository = PostgresProductImageRepository(db_conn)
    await product_repository.add(product)
    first = make_image(product_id=product.id, sort_order=5)
    second = make_image(product_id=product.id, sort_order=9)
    third = make_image(product_id=product.id, sort_order=1)
    await image_repository.add(first)
    await image_repository.add(second)
    await image_repository.add(third)

    await image_repository.reorder(product.id, [third.id, first.id, second.id])

    rows = await db_conn.fetch(
        "SELECT id, sort_order FROM product_images WHERE product_id = $1 ORDER BY sort_order",
        product.id,
    )
    ordered_ids = [row["id"] for row in rows]
    assert ordered_ids == [third.id, first.id, second.id]
    assert [row["sort_order"] for row in rows] == [0, 1, 2]


async def test_update_alt_text_changes_only_alt_text(db_conn) -> None:
    """spec: product-persistence "adapters agree on image operations",
    extended by design.md DD3's `update_alt_text` port method.
    """
    product = make_product()
    product_repository = PostgresProductRepository(db_conn)
    image_repository = PostgresProductImageRepository(db_conn)
    await product_repository.add(product)
    image = make_image(product_id=product.id, alt_text="")
    await image_repository.add(image)

    await image_repository.update_alt_text(image.id, "A red case")

    updated = await image_repository.get_by_id(image.id)
    assert updated is not None
    assert updated.alt_text == "A red case"
    assert updated.storage_path == image.storage_path
    assert updated.sort_order == image.sort_order
    assert updated.variant_id == image.variant_id


async def test_update_alt_text_unknown_image_raises_image_not_found_error(db_conn) -> None:
    image_repository = PostgresProductImageRepository(db_conn)

    with pytest.raises(ImageNotFoundError):
        await image_repository.update_alt_text(uuid4(), "whatever")


async def test_get_by_id_returns_none_for_unknown_id(db_conn) -> None:
    image_repository = PostgresProductImageRepository(db_conn)

    assert await image_repository.get_by_id(uuid4()) is None


async def test_delete_is_a_hard_delete(db_conn) -> None:
    """proposal.md decision 2 -- images are HARD deleted, unlike the
    soft-delete used for products/variants.
    """
    product = make_product()
    product_repository = PostgresProductRepository(db_conn)
    image_repository = PostgresProductImageRepository(db_conn)
    await product_repository.add(product)
    image = make_image(product_id=product.id)
    await image_repository.add(image)

    await image_repository.delete(image.id)

    row_count = await db_conn.fetchval(
        "SELECT count(*) FROM product_images WHERE id = $1", image.id
    )
    assert row_count == 0


async def test_delete_unknown_image_raises_image_not_found_error(db_conn) -> None:
    image_repository = PostgresProductImageRepository(db_conn)

    with pytest.raises(ImageNotFoundError):
        await image_repository.delete(uuid4())


async def test_next_sort_order_is_independent_per_hero_and_variant_group(
    db_conn,
) -> None:
    variant = ProductVariant(
        id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
    )
    product = make_product(variants=[variant])
    product_repository = PostgresProductRepository(db_conn)
    image_repository = PostgresProductImageRepository(db_conn)
    await product_repository.add(product)

    assert await image_repository.next_sort_order(product.id, None) == 0
    assert await image_repository.next_sort_order(product.id, variant.id) == 0

    await image_repository.add(make_image(product_id=product.id, variant_id=None, sort_order=0))
    await image_repository.add(
        make_image(product_id=product.id, variant_id=variant.id, sort_order=0)
    )
    await image_repository.add(
        make_image(product_id=product.id, variant_id=variant.id, sort_order=1)
    )

    assert await image_repository.next_sort_order(product.id, None) == 1
    assert await image_repository.next_sort_order(product.id, variant.id) == 2
