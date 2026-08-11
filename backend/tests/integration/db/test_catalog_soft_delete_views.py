"""Integration tests for the public catalog views' soft-delete filtering,
against real local Postgres (migration `20260811000000_products_soft_delete.sql`).

Uses `db_conn` (per-test rollback isolation, see `tests/conftest.py`).
`product_images` has no port/adapter at all yet, so rows are inserted via
raw SQL directly.

Retire helpers below use raw SQL `UPDATE ... SET deleted_at = now()` --
PR1's original proof, kept as-is. The `*_via_port_method` tests further
down (PR2, task 2.17) re-run the same view assertions using the new
`soft_delete`/`soft_delete_variant` port methods instead, confirming
parity: the port methods produce the exact same DB state the raw-SQL proof
already relied on.
"""

from decimal import Decimal
from uuid import uuid4

import asyncpg

from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)


async def _insert_image(
    conn: asyncpg.Connection,
    *,
    product_id: object,
    variant_id: object | None,
    storage_path: str,
) -> None:
    await conn.execute(
        "INSERT INTO product_images (id, product_id, variant_id, storage_path) "
        "VALUES ($1, $2, $3, $4)",
        uuid4(),
        product_id,
        variant_id,
        storage_path,
    )


async def _retire_product(conn: asyncpg.Connection, product_id: object) -> None:
    await conn.execute(
        "UPDATE products SET deleted_at = now() WHERE id = $1", product_id
    )


async def _retire_variant(conn: asyncpg.Connection, variant_id: object) -> None:
    await conn.execute(
        "UPDATE product_variants SET deleted_at = now() WHERE id = $1", variant_id
    )


def _make_product(**overrides: object) -> Product:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "slug": f"funda-soft-delete-{uuid4().hex[:8]}",
        "name": "Funda de prueba",
        "model": "iPhone 13",
        "variants": [
            ProductVariant(
                id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
            )
        ],
    }
    defaults.update(overrides)
    return Product(**defaults)  # type: ignore[arg-type]


async def test_retiring_a_product_removes_it_from_all_three_catalog_views(
    db_conn,
) -> None:
    repository = PostgresProductRepository(db_conn)
    product = _make_product()
    await repository.add(product)
    variant_id = product.variants[0].id
    await _insert_image(
        db_conn, product_id=product.id, variant_id=None, storage_path="hero.jpg"
    )
    await _insert_image(
        db_conn, product_id=product.id, variant_id=variant_id, storage_path="negro.jpg"
    )

    await _retire_product(db_conn, product.id)

    product_row = await db_conn.fetchrow(
        "SELECT 1 FROM catalog_products WHERE id = $1", product.id
    )
    variant_rows = await db_conn.fetch(
        "SELECT 1 FROM catalog_variants WHERE product_id = $1", product.id
    )
    image_rows = await db_conn.fetch(
        "SELECT 1 FROM catalog_product_images WHERE product_id = $1", product.id
    )

    assert product_row is None
    assert variant_rows == []
    assert image_rows == []


async def test_retiring_one_variant_hides_only_that_variant_and_its_image(
    db_conn,
) -> None:
    repository = PostgresProductRepository(db_conn)
    variant_a = ProductVariant(
        id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
    )
    variant_b = ProductVariant(
        id=uuid4(), color="Rojo", price=Decimal("47000.00"), cost=Decimal("31000.00")
    )
    product = _make_product(variants=[variant_a, variant_b])
    await repository.add(product)
    await _insert_image(
        db_conn, product_id=product.id, variant_id=None, storage_path="hero.jpg"
    )
    await _insert_image(
        db_conn, product_id=product.id, variant_id=variant_a.id, storage_path="negro.jpg"
    )
    await _insert_image(
        db_conn, product_id=product.id, variant_id=variant_b.id, storage_path="rojo.jpg"
    )

    await _retire_variant(db_conn, variant_a.id)

    product_row = await db_conn.fetchrow(
        "SELECT 1 FROM catalog_products WHERE id = $1", product.id
    )
    variant_ids = {
        row["id"]
        for row in await db_conn.fetch(
            "SELECT id FROM catalog_variants WHERE product_id = $1", product.id
        )
    }
    image_paths = {
        row["storage_path"]
        for row in await db_conn.fetch(
            "SELECT storage_path FROM catalog_product_images WHERE product_id = $1",
            product.id,
        )
    }

    assert product_row is not None
    assert variant_a.id not in variant_ids
    assert variant_b.id in variant_ids
    assert "negro.jpg" not in image_paths
    assert "hero.jpg" in image_paths
    assert "rojo.jpg" in image_paths


async def test_a_live_untouched_product_is_unaffected_by_a_sibling_retirement(
    db_conn,
) -> None:
    repository = PostgresProductRepository(db_conn)
    retired_product = _make_product()
    live_product = _make_product()
    await repository.add(retired_product)
    await repository.add(live_product)
    await _insert_image(
        db_conn,
        product_id=live_product.id,
        variant_id=None,
        storage_path="live-hero.jpg",
    )

    await _retire_product(db_conn, retired_product.id)

    live_row = await db_conn.fetchrow(
        "SELECT slug FROM catalog_products WHERE id = $1", live_product.id
    )
    live_variant_rows = await db_conn.fetch(
        "SELECT 1 FROM catalog_variants WHERE product_id = $1", live_product.id
    )
    live_image_rows = await db_conn.fetch(
        "SELECT 1 FROM catalog_product_images WHERE product_id = $1", live_product.id
    )
    retired_row = await db_conn.fetchrow(
        "SELECT 1 FROM catalog_products WHERE id = $1", retired_product.id
    )

    assert live_row is not None
    assert live_row["slug"] == live_product.slug
    assert len(live_variant_rows) == 1
    assert len(live_image_rows) == 1
    assert retired_row is None


async def test_retiring_a_product_via_port_method_removes_it_from_all_three_views(
    db_conn,
) -> None:
    """Parity with `test_retiring_a_product_removes_it_from_all_three_catalog_views`
    (PR1's raw-SQL proof), using `repository.soft_delete` instead.
    """
    repository = PostgresProductRepository(db_conn)
    product = _make_product()
    await repository.add(product)
    variant_id = product.variants[0].id
    await _insert_image(
        db_conn, product_id=product.id, variant_id=None, storage_path="hero.jpg"
    )
    await _insert_image(
        db_conn, product_id=product.id, variant_id=variant_id, storage_path="negro.jpg"
    )

    await repository.soft_delete(product.id)

    product_row = await db_conn.fetchrow(
        "SELECT 1 FROM catalog_products WHERE id = $1", product.id
    )
    variant_rows = await db_conn.fetch(
        "SELECT 1 FROM catalog_variants WHERE product_id = $1", product.id
    )
    image_rows = await db_conn.fetch(
        "SELECT 1 FROM catalog_product_images WHERE product_id = $1", product.id
    )

    assert product_row is None
    assert variant_rows == []
    assert image_rows == []


async def test_retiring_one_variant_via_port_method_hides_only_that_variant_and_its_image(
    db_conn,
) -> None:
    """Parity with `test_retiring_one_variant_hides_only_that_variant_and_its_image`
    (PR1's raw-SQL proof), using `repository.soft_delete_variant` instead.
    """
    repository = PostgresProductRepository(db_conn)
    variant_a = ProductVariant(
        id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
    )
    variant_b = ProductVariant(
        id=uuid4(), color="Rojo", price=Decimal("47000.00"), cost=Decimal("31000.00")
    )
    product = _make_product(variants=[variant_a, variant_b])
    await repository.add(product)
    await _insert_image(
        db_conn, product_id=product.id, variant_id=None, storage_path="hero.jpg"
    )
    await _insert_image(
        db_conn, product_id=product.id, variant_id=variant_a.id, storage_path="negro.jpg"
    )
    await _insert_image(
        db_conn, product_id=product.id, variant_id=variant_b.id, storage_path="rojo.jpg"
    )

    await repository.soft_delete_variant(product.id, variant_a.id)

    product_row = await db_conn.fetchrow(
        "SELECT 1 FROM catalog_products WHERE id = $1", product.id
    )
    variant_ids = {
        row["id"]
        for row in await db_conn.fetch(
            "SELECT id FROM catalog_variants WHERE product_id = $1", product.id
        )
    }
    image_paths = {
        row["storage_path"]
        for row in await db_conn.fetch(
            "SELECT storage_path FROM catalog_product_images WHERE product_id = $1",
            product.id,
        )
    }

    assert product_row is not None
    assert variant_a.id not in variant_ids
    assert variant_b.id in variant_ids
    assert "negro.jpg" not in image_paths
    assert "hero.jpg" in image_paths
    assert "rojo.jpg" in image_paths
