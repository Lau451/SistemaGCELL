"""Integration tests for Row-Level-Security policies on the base catalog and
inventory tables, plus the public catalog views' read boundary, against real
Postgres role switching (`SET ROLE`).

Part A of the RLS module (the read boundary, PR 3 of the `ci-and-rls-tests`
chain): `anon`/`authenticated` denial on the base tables, the privilege
matrix, the catalog views, soft-delete filtering, and the internal-only
`variant_stock_levels` view.

Part B (this same module, PR 4 of the chain, see design.md DD5): `service_role`
full CRUD on `products`/`product_variants`/`product_images` (proves
`BYPASSRLS` + the explicit `GRANT` together), the `stock_movements`
grant-layer split (`service_role` may `SELECT`/`INSERT` but not
`UPDATE`/`DELETE` -- a missing `GRANT`, not the append-only trigger), the
append-only trigger itself (the table owner/superuser -- who has every
privilege and bypasses RLS -- is still rejected by
`reject_stock_movements_mutation`), and the `storage.objects` matrix (public
read scoped to the `product-photos` bucket, `service_role`-only write).

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
PRIVILEGED_ROLE = "service_role"


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


# --- content-ai-domains PR1 (1.1): short_description column on catalog_products


@pytest.mark.parametrize("role", RESTRICTED_ROLES)
async def test_restricted_role_reads_short_description_null_on_existing_row(
    db_conn: asyncpg.Connection, role: str
) -> None:
    """`short_description` (new column, D3/DD7) must be selectable from
    `catalog_products` and must read back `null` on a row seeded before this
    column carried any value -- the migration is purely additive, so an
    existing product's `short_description` has no way to be anything but
    `null`. Also proves `anon`/`authenticated` can still read the view at
    all after the `create or replace view` (product-catalog-schema spec
    scenarios "Short_description defaults to null on existing rows" and
    "Anon can still read the catalog view after the migration").
    """
    product = await _seed_one_product_variant_image(db_conn)

    async with as_role(db_conn, role) as conn:
        row = await conn.fetchrow(
            "SELECT short_description FROM catalog_products WHERE id = $1", product.id
        )

    assert row is not None
    assert row["short_description"] is None


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


# ============================================================================
# Part B (PR 4): service_role CRUD, the stock_movements grant-layer split,
# the append-only trigger, and the storage.objects matrix.
# ============================================================================


async def _seed_two_bucket_storage_objects(
    db_conn: asyncpg.Connection,
) -> tuple[str, str, str]:
    """Seed the real `product-photos` bucket (idempotent -- already created
    by `20260810000502_storage_product_photos.sql`) plus a second, unrelated
    bucket, each holding exactly one object, as superuser. Returns
    `(other_bucket_id, product_photos_object_name, other_bucket_object_name)`
    so callers can assert scoping by object identity, not just a row count.
    """
    other_bucket_id = f"rls-test-other-{uuid4().hex[:8]}"
    product_photos_name = f"rls-test-hero-{uuid4().hex[:8]}.jpg"
    other_bucket_name = f"rls-test-secret-{uuid4().hex[:8]}.jpg"

    await db_conn.execute(
        "INSERT INTO storage.buckets (id, name, public) "
        "VALUES ('product-photos', 'product-photos', true) "
        "ON CONFLICT (id) DO NOTHING"
    )
    await db_conn.execute(
        "INSERT INTO storage.buckets (id, name, public) VALUES ($1, $1, false)",
        other_bucket_id,
    )
    await db_conn.execute(
        "INSERT INTO storage.objects (id, bucket_id, name) VALUES ($1, 'product-photos', $2)",
        uuid4(),
        product_photos_name,
    )
    await db_conn.execute(
        "INSERT INTO storage.objects (id, bucket_id, name) VALUES ($1, $2, $3)",
        uuid4(),
        other_bucket_id,
        other_bucket_name,
    )
    return other_bucket_id, product_photos_name, other_bucket_name


# --- 4.1/4.2: service_role full CRUD on products/product_variants/product_images


async def test_service_role_full_crud_on_products_variants_and_images(
    db_conn: asyncpg.Connection,
) -> None:
    """INSERT -> UPDATE -> DELETE on all 3 service_role-writable base
    tables, entirely inside one `as_role` block (writes made inside
    `as_role` are only visible for the lifetime of that block -- see its
    docstring -- so the full CRUD chain must run in a single block to build
    on itself). This succeeds only because `BYPASSRLS` (RLS bypass) and the
    explicit `GRANT` (table privilege) are both present: the base tables
    have RLS enabled with zero policies, so a role with the `GRANT` alone
    would still be rejected -- proven separately below without touching the
    real `service_role` role (see apply-progress.md's task 4.1 RED note).
    """
    product_id = uuid4()
    variant_id = uuid4()
    image_id = uuid4()

    async with as_role(db_conn, PRIVILEGED_ROLE) as conn:
        await conn.execute(
            "INSERT INTO products (id, slug, name, model) VALUES ($1, $2, $3, $4)",
            product_id,
            f"funda-rls-service-{uuid4().hex[:8]}",
            "Funda service_role",
            "iPhone 14",
        )
        await conn.execute(
            "INSERT INTO product_variants (id, product_id, color, price, cost) "
            "VALUES ($1, $2, $3, $4, $5)",
            variant_id,
            product_id,
            "Azul",
            Decimal("50000.00"),
            Decimal("35000.00"),
        )
        await conn.execute(
            "INSERT INTO product_images (id, product_id, variant_id, storage_path) "
            "VALUES ($1, $2, $3, $4)",
            image_id,
            product_id,
            variant_id,
            "azul.jpg",
        )
        inserted_count = await conn.fetchval(
            "SELECT count(*) FROM products WHERE id = $1", product_id
        )
        assert inserted_count == 1

        await conn.execute(
            "UPDATE products SET name = 'Funda actualizada' WHERE id = $1", product_id
        )
        await conn.execute(
            "UPDATE product_variants SET price = $1 WHERE id = $2",
            Decimal("52000.00"),
            variant_id,
        )
        await conn.execute(
            "UPDATE product_images SET alt_text = $1 WHERE id = $2",
            "azul updated",
            image_id,
        )
        updated_name = await conn.fetchval(
            "SELECT name FROM products WHERE id = $1", product_id
        )
        updated_price = await conn.fetchval(
            "SELECT price FROM product_variants WHERE id = $1", variant_id
        )
        assert updated_name == "Funda actualizada"
        assert updated_price == Decimal("52000.00")

        await conn.execute("DELETE FROM product_images WHERE id = $1", image_id)
        await conn.execute("DELETE FROM product_variants WHERE id = $1", variant_id)
        await conn.execute("DELETE FROM products WHERE id = $1", product_id)
        remaining_count = await conn.fetchval(
            "SELECT count(*) FROM products WHERE id = $1", product_id
        )
        assert remaining_count == 0


# --- 4.3: stock_movements grant-layer split (DD5 #1) ------------------------


async def test_service_role_select_and_insert_succeed_on_stock_movements(
    db_conn: asyncpg.Connection,
) -> None:
    product = await _seed_one_product_variant_image(db_conn)
    variant_id = product.variants[0].id

    async with as_role(db_conn, PRIVILEGED_ROLE) as conn:
        await conn.execute(
            "INSERT INTO stock_movements (variant_id, movement_type, quantity_delta) "
            "VALUES ($1, 'restock', 5)",
            variant_id,
        )
        count = await conn.fetchval(
            "SELECT count(*) FROM stock_movements WHERE variant_id = $1", variant_id
        )

    assert count == 1


async def test_service_role_update_denied_on_stock_movements(
    db_conn: asyncpg.Connection,
) -> None:
    product = await _seed_one_product_variant_image(db_conn)
    variant_id = product.variants[0].id
    movement_id = await db_conn.fetchval(
        "INSERT INTO stock_movements (variant_id, movement_type, quantity_delta) "
        "VALUES ($1, 'restock', 5) RETURNING id",
        variant_id,
    )

    async with as_role(db_conn, PRIVILEGED_ROLE) as conn:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.execute(
                "UPDATE stock_movements SET reason = 'oops' WHERE id = $1", movement_id
            )


async def test_service_role_delete_denied_on_stock_movements(
    db_conn: asyncpg.Connection,
) -> None:
    product = await _seed_one_product_variant_image(db_conn)
    variant_id = product.variants[0].id
    movement_id = await db_conn.fetchval(
        "INSERT INTO stock_movements (variant_id, movement_type, quantity_delta) "
        "VALUES ($1, 'restock', 5) RETURNING id",
        variant_id,
    )

    async with as_role(db_conn, PRIVILEGED_ROLE) as conn:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.execute("DELETE FROM stock_movements WHERE id = $1", movement_id)


# --- 4.4: append-only trigger, owner/superuser layer (DD5 #2) ---------------


async def test_owner_update_denied_by_append_only_trigger_on_stock_movements(
    db_conn: asyncpg.Connection,
) -> None:
    """`db_conn` itself is the owner/superuser connection (not `service_role`
    -- DD5's point is that `service_role` never reaches this layer, it is
    already stopped by the missing GRANT in the test above). Owner/superuser
    has every privilege and bypasses RLS, so this UPDATE clears the ACL/RLS
    layer entirely and is rejected only by `reject_stock_movements_mutation`.
    `pytest.raises` wraps the nested `transaction()` block itself (not a
    statement inside it) so the raised error propagates through
    `Transaction.__aexit__`, which issues `ROLLBACK TO SAVEPOINT` -- the
    correct way to recover a sub-transaction after an expected exception.
    """
    product = await _seed_one_product_variant_image(db_conn)
    variant_id = product.variants[0].id
    movement_id = await db_conn.fetchval(
        "INSERT INTO stock_movements (variant_id, movement_type, quantity_delta) "
        "VALUES ($1, 'restock', 5) RETURNING id",
        variant_id,
    )

    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        async with db_conn.transaction():
            await db_conn.execute(
                "UPDATE stock_movements SET reason = 'oops' WHERE id = $1", movement_id
            )


async def test_owner_delete_denied_by_append_only_trigger_on_stock_movements(
    db_conn: asyncpg.Connection,
) -> None:
    product = await _seed_one_product_variant_image(db_conn)
    variant_id = product.variants[0].id
    movement_id = await db_conn.fetchval(
        "INSERT INTO stock_movements (variant_id, movement_type, quantity_delta) "
        "VALUES ($1, 'restock', 5) RETURNING id",
        variant_id,
    )

    with pytest.raises(asyncpg.exceptions.RaiseError, match="append-only"):
        async with db_conn.transaction():
            await db_conn.execute("DELETE FROM stock_movements WHERE id = $1", movement_id)


# --- 4.5: storage.objects -- public read scoped to product-photos, ----------
# --- service_role-only write -------------------------------------------------


@pytest.mark.parametrize("role", RESTRICTED_ROLES)
async def test_restricted_role_reads_only_product_photos_bucket_objects(
    db_conn: asyncpg.Connection, role: str
) -> None:
    _, product_photos_name, other_bucket_name = await _seed_two_bucket_storage_objects(
        db_conn
    )

    async with as_role(db_conn, role) as conn:
        rows = await conn.fetch(
            "SELECT name FROM storage.objects WHERE name = ANY($1)",
            [product_photos_name, other_bucket_name],
        )

    names = {row["name"] for row in rows}
    assert names == {product_photos_name}
    assert other_bucket_name not in names


async def test_anon_insert_denied_on_storage_objects(db_conn: asyncpg.Connection) -> None:
    async with as_role(db_conn, "anon") as conn:
        with pytest.raises(asyncpg.exceptions.InsufficientPrivilegeError):
            await conn.execute(
                "INSERT INTO storage.objects (id, bucket_id, name) VALUES ($1, $2, $3)",
                uuid4(),
                "product-photos",
                f"rls-test-anon-insert-{uuid4().hex[:8]}.jpg",
            )


async def test_anon_update_affects_zero_rows_on_storage_objects(
    db_conn: asyncpg.Connection,
) -> None:
    _, product_photos_name, _ = await _seed_two_bucket_storage_objects(db_conn)

    async with as_role(db_conn, "anon") as conn:
        result = await conn.execute(
            "UPDATE storage.objects SET name = $1 WHERE name = $2",
            f"renamed-{uuid4().hex[:8]}.jpg",
            product_photos_name,
        )

    assert result == "UPDATE 0"


async def test_anon_delete_affects_zero_rows_on_storage_objects(
    db_conn: asyncpg.Connection,
) -> None:
    """The real local Supabase Storage schema adds a statement-level trigger
    (`storage.protect_delete`) that rejects ANY direct `DELETE` on
    `storage.objects` unless the session sets `storage.allow_delete_query`
    -- a Storage-*service* safety net, not an RLS policy, and not part of
    CI's minimal stub (design.md DD1's documented fidelity gap). Setting
    that GUC neutralizes the local-only guard so this assertion exercises
    the actual RLS policy layer identically on both environments: an
    unrecognized custom (`namespace.name`) GUC is a harmless no-op
    placeholder on CI's vanilla `postgres:17`, which has no such trigger to
    begin with.
    """
    _, product_photos_name, _ = await _seed_two_bucket_storage_objects(db_conn)

    async with as_role(db_conn, "anon") as conn:
        await conn.execute("SET LOCAL storage.allow_delete_query = 'true'")
        result = await conn.execute(
            "DELETE FROM storage.objects WHERE name = $1", product_photos_name
        )

    assert result == "DELETE 0"


async def test_service_role_insert_succeeds_on_storage_objects(
    db_conn: asyncpg.Connection,
) -> None:
    object_name = f"rls-test-sr-insert-{uuid4().hex[:8]}.jpg"

    async with as_role(db_conn, PRIVILEGED_ROLE) as conn:
        await conn.execute(
            "INSERT INTO storage.objects (id, bucket_id, name) VALUES ($1, $2, $3)",
            uuid4(),
            "product-photos",
            object_name,
        )
        count = await conn.fetchval(
            "SELECT count(*) FROM storage.objects WHERE name = $1", object_name
        )

    assert count == 1
