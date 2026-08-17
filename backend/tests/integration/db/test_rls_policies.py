"""Integration tests for Row-Level-Security policies on the base catalog and
inventory tables, plus the public catalog views' read boundary, against real
Postgres role switching (`SET ROLE`).

Part A of the RLS module (the read boundary, PR 3 of the `ci-and-rls-tests`
chain): `anon`/`authenticated` denial on the base tables, the privilege
matrix, the catalog views, soft-delete filtering, and the internal-only
`variant_stock_levels` view. `service_role` CRUD, the `stock_movements`
grant-layer split, the append-only trigger, and the storage matrix are Part B
(see design.md DD5) and are added to this same module in a later PR.

Uses `db_conn` (per-test rollback isolation, see `tests/conftest.py`) --
UNCHANGED, per D5/DD4. Fixture rows are written as superuser *inside* the
same outer transaction `db_conn` already holds, then read back after
switching role via `as_role()`, a module-local SAVEPOINT helper (DD4): a
denied statement aborts the enclosing transaction, so every role-scoped
block runs inside its own nested transaction (asyncpg SAVEPOINT) to stay
recoverable, and rolling the SAVEPOINT back also restores `SET LOCAL ROLE`
for the next block.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from decimal import Decimal
from uuid import uuid4

import asyncpg
import pytest

from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)

BASE_TABLES = ("products", "product_variants", "product_images", "stock_movements")
CATALOG_VIEWS = ("catalog_products", "catalog_variants", "catalog_product_images")
RESTRICTED_ROLES = ("anon", "authenticated")
PRIVILEGES = ("select", "insert", "update", "delete")


@asynccontextmanager
async def as_role(conn: asyncpg.Connection, role: str) -> AsyncIterator[asyncpg.Connection]:
    """Run a block as `role` inside a SAVEPOINT.

    Two reasons for the savepoint, both mandatory:
    1. A denied statement aborts the transaction; without it every later
       statement raises InFailedSQLTransactionError instead of its own error.
    2. Rolling back restores `SET LOCAL ROLE`, returning the caller to the
       superuser `db_conn` connected as.
    `role` is always a literal from the constants above -- never test input --
    so the quoted-identifier f-string carries no injection surface.
    """
    savepoint = conn.transaction()
    await savepoint.start()
    await conn.execute(f'SET LOCAL ROLE "{role}"')
    try:
        yield conn
    finally:
        await savepoint.rollback()


def _make_product(**overrides: object) -> Product:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "slug": f"funda-rls-{uuid4().hex[:8]}",
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
    await conn.execute("UPDATE products SET deleted_at = now() WHERE id = $1", product_id)


async def _retire_variant(conn: asyncpg.Connection, variant_id: object) -> None:
    await conn.execute(
        "UPDATE product_variants SET deleted_at = now() WHERE id = $1", variant_id
    )


async def _seed_one_product_variant_image(db_conn: asyncpg.Connection) -> Product:
    """Seed one product + its single variant + one hero image, as superuser."""
    repository = PostgresProductRepository(db_conn)
    product = _make_product()
    await repository.add(product)
    await _insert_image(
        db_conn, product_id=product.id, variant_id=None, storage_path="hero.jpg"
    )
    return product


# --- 3.2: anon/authenticated SELECT denied on all base tables -------------


@pytest.mark.parametrize("role", RESTRICTED_ROLES)
@pytest.mark.parametrize("table", BASE_TABLES)
async def test_restricted_role_select_denied_on_base_table(
    db_conn: asyncpg.Connection, table: str, role: str
) -> None:
    async with as_role(db_conn, role) as conn:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.fetch(f"SELECT 1 FROM {table} LIMIT 1")


# --- 3.3: full privilege matrix, no SET ROLE needed ------------------------


@pytest.mark.parametrize("privilege", PRIVILEGES)
@pytest.mark.parametrize("table", BASE_TABLES)
@pytest.mark.parametrize("role", RESTRICTED_ROLES)
async def test_restricted_role_has_no_privilege_on_base_table(
    db_conn: asyncpg.Connection, role: str, table: str, privilege: str
) -> None:
    has_privilege = await db_conn.fetchval(
        "SELECT has_table_privilege($1, $2, $3)", role, table, privilege
    )
    assert has_privilege is False


# --- 3.4: both restricted roles read the catalog views ---------------------


@pytest.mark.parametrize("role", RESTRICTED_ROLES)
@pytest.mark.parametrize("view", CATALOG_VIEWS)
async def test_restricted_role_can_read_seeded_row_from_catalog_view(
    db_conn: asyncpg.Connection, view: str, role: str
) -> None:
    product = await _seed_one_product_variant_image(db_conn)

    async with as_role(db_conn, role) as conn:
        if view == "catalog_products":
            count = await conn.fetchval(
                "SELECT count(*) FROM catalog_products WHERE id = $1", product.id
            )
        elif view == "catalog_variants":
            count = await conn.fetchval(
                "SELECT count(*) FROM catalog_variants WHERE product_id = $1", product.id
            )
        else:
            count = await conn.fetchval(
                "SELECT count(*) FROM catalog_product_images WHERE product_id = $1",
                product.id,
            )

    assert count == 1


# --- 3.5: soft-delete filtering, as seen by anon ---------------------------


async def test_retiring_the_product_hides_it_from_all_three_views_for_anon(
    db_conn: asyncpg.Connection,
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

    async with as_role(db_conn, "anon") as conn:
        product_count = await conn.fetchval(
            "SELECT count(*) FROM catalog_products WHERE id = $1", product.id
        )
        variant_count = await conn.fetchval(
            "SELECT count(*) FROM catalog_variants WHERE product_id = $1", product.id
        )
        image_count = await conn.fetchval(
            "SELECT count(*) FROM catalog_product_images WHERE product_id = $1", product.id
        )

    assert product_count == 0
    assert variant_count == 0
    assert image_count == 0


async def test_retiring_one_variant_hides_only_that_variant_and_its_image_for_anon(
    db_conn: asyncpg.Connection,
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

    async with as_role(db_conn, "anon") as conn:
        product_count = await conn.fetchval(
            "SELECT count(*) FROM catalog_products WHERE id = $1", product.id
        )
        variant_ids = {
            row["id"]
            for row in await conn.fetch(
                "SELECT id FROM catalog_variants WHERE product_id = $1", product.id
            )
        }
        image_paths = {
            row["storage_path"]
            for row in await conn.fetch(
                "SELECT storage_path FROM catalog_product_images WHERE product_id = $1",
                product.id,
            )
        }

    assert product_count == 1
    assert variant_a.id not in variant_ids
    assert variant_b.id in variant_ids
    assert "negro.jpg" not in image_paths
    assert "hero.jpg" in image_paths
    assert "rojo.jpg" in image_paths


async def test_a_live_sibling_product_stays_visible_to_anon_after_a_retirement(
    db_conn: asyncpg.Connection,
) -> None:
    repository = PostgresProductRepository(db_conn)
    retired_product = _make_product()
    live_product = _make_product()
    await repository.add(retired_product)
    await repository.add(live_product)
    await _insert_image(
        db_conn, product_id=live_product.id, variant_id=None, storage_path="live-hero.jpg"
    )

    await _retire_product(db_conn, retired_product.id)

    async with as_role(db_conn, "anon") as conn:
        live_row = await conn.fetchrow(
            "SELECT slug FROM catalog_products WHERE id = $1", live_product.id
        )
        live_variant_count = await conn.fetchval(
            "SELECT count(*) FROM catalog_variants WHERE product_id = $1", live_product.id
        )
        live_image_count = await conn.fetchval(
            "SELECT count(*) FROM catalog_product_images WHERE product_id = $1",
            live_product.id,
        )
        retired_count = await conn.fetchval(
            "SELECT count(*) FROM catalog_products WHERE id = $1", retired_product.id
        )

    assert live_row is not None
    assert live_row["slug"] == live_product.slug
    assert live_variant_count == 1
    assert live_image_count == 1
    assert retired_count == 0


# --- 3.6: variant_stock_levels is internal-only -----------------------------


@pytest.mark.parametrize("role", RESTRICTED_ROLES)
async def test_restricted_role_has_no_select_privilege_on_variant_stock_levels(
    db_conn: asyncpg.Connection, role: str
) -> None:
    has_select = await db_conn.fetchval(
        "SELECT has_table_privilege($1, 'variant_stock_levels', 'select')", role
    )
    assert has_select is False


@pytest.mark.parametrize("role", RESTRICTED_ROLES)
async def test_restricted_role_is_denied_reading_variant_stock_levels(
    db_conn: asyncpg.Connection, role: str
) -> None:
    async with as_role(db_conn, role) as conn:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.fetch("SELECT 1 FROM variant_stock_levels LIMIT 1")
