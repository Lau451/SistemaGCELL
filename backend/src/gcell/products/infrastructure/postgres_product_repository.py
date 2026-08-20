"""Postgres adapter for `ProductRepository`.

Takes an `asyncpg.Connection` (never a `Pool`) so the caller always controls
the transaction boundary via `shared.infrastructure.postgres.transaction()`
-- see design.md "transaction boundary at the composition root". Non-
transactional use is impossible without deliberately calling `pool.acquire()`
yourself.

`Product.id`/`ProductVariant.id` are client-generated (`uuid4()`) before
insert, not `RETURNING`-fetched: id-based equality (see
`products/domain/product.py`) requires a complete entity before it is ever
persisted -- see design.md "client-generated UUIDs and one LEFT JOIN read".
"""

from uuid import UUID

import asyncpg

from gcell.products.application.exceptions import (
    DuplicateProductSlugError,
    ProductNotFoundError,
    VariantNotFoundError,
)
from gcell.products.domain.product import Product, ProductVariant
from gcell.shared.infrastructure.postgres import transaction

_SELECT_COLUMNS = """
    p.id, p.slug, p.name, p.model, p.description, p.short_description,
    v.id AS variant_id, v.color, v.price, v.cost
"""

_SELECT_BY_SLUG = f"""
    SELECT {_SELECT_COLUMNS}
    FROM products p
    LEFT JOIN product_variants v ON v.product_id = p.id AND v.deleted_at IS NULL
    WHERE p.slug = $1 AND p.deleted_at IS NULL
    ORDER BY v.created_at, v.id
"""

_SELECT_BY_ID = f"""
    SELECT {_SELECT_COLUMNS}
    FROM products p
    LEFT JOIN product_variants v ON v.product_id = p.id AND v.deleted_at IS NULL
    WHERE p.id = $1 AND p.deleted_at IS NULL
    ORDER BY v.created_at, v.id
"""

_SELECT_ALL = f"""
    SELECT {_SELECT_COLUMNS}
    FROM products p
    LEFT JOIN product_variants v ON v.product_id = p.id AND v.deleted_at IS NULL
    WHERE p.deleted_at IS NULL
    ORDER BY p.created_at, p.id, v.created_at, v.id
"""

_INSERT_PRODUCT = """
    INSERT INTO products (id, slug, name, model, description, short_description)
    VALUES ($1, $2, $3, $4, $5, $6)
"""

_INSERT_VARIANT = """
    INSERT INTO product_variants (id, product_id, color, price, cost)
    VALUES ($1, $2, $3, $4, $5)
"""

_UPDATE_PRODUCT_FIELDS = """
    UPDATE products SET name = $2, model = $3, description = $4, short_description = $5
    WHERE id = $1 AND deleted_at IS NULL
"""

_UPSERT_VARIANT = """
    INSERT INTO product_variants (id, product_id, color, price, cost)
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (id) DO UPDATE SET color = $3, price = $4, cost = $5
"""

_SOFT_DELETE_PRODUCT = """
    UPDATE products SET deleted_at = now() WHERE id = $1 AND deleted_at IS NULL
"""

_SOFT_DELETE_VARIANT = """
    UPDATE product_variants SET deleted_at = now()
    WHERE id = $1 AND product_id = $2 AND deleted_at IS NULL
"""

_SLUG_EXISTS = "SELECT EXISTS(SELECT 1 FROM products WHERE slug = $1)"


def _rows_affected(command_tag: str) -> int:
    """asyncpg's `execute()` returns a command tag like `"UPDATE 1"` --
    parse the trailing row count."""
    return int(command_tag.rsplit(" ", 1)[-1])


def _row_to_variant(row: asyncpg.Record) -> ProductVariant:
    return ProductVariant(
        id=row["variant_id"],
        color=row["color"],
        price=row["price"],
        cost=row["cost"],
    )


def _rows_to_product(rows: list[asyncpg.Record]) -> Product:
    first = rows[0]
    variants = [
        _row_to_variant(row) for row in rows if row["variant_id"] is not None
    ]
    return Product(
        id=first["id"],
        slug=first["slug"],
        name=first["name"],
        model=first["model"],
        variants=variants,
        description=first["description"],
        short_description=first["short_description"],
    )


def _rows_to_products(rows: list[asyncpg.Record]) -> list[Product]:
    """Group `_SELECT_ALL`'s flat LEFT JOIN rows by product id.

    Rows are already ordered by `p.id`, so a simple run-length grouping is
    enough -- no need for `itertools.groupby`'s stricter contiguity setup.
    """
    products: list[Product] = []
    current_id: UUID | None = None
    current_rows: list[asyncpg.Record] = []

    for row in rows:
        if row["id"] != current_id:
            if current_rows:
                products.append(_rows_to_product(current_rows))
            current_id = row["id"]
            current_rows = []
        current_rows.append(row)

    if current_rows:
        products.append(_rows_to_product(current_rows))

    return products


class PostgresProductRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def add(self, product: Product) -> None:
        try:
            async with transaction(self._conn) as conn:
                await conn.execute(
                    _INSERT_PRODUCT,
                    product.id,
                    product.slug,
                    product.name,
                    product.model,
                    product.description,
                    product.short_description,
                )
                if product.variants:
                    await conn.executemany(
                        _INSERT_VARIANT,
                        [
                            (variant.id, product.id, variant.color, variant.price, variant.cost)
                            for variant in product.variants
                        ],
                    )
        except asyncpg.UniqueViolationError as exc:
            if exc.constraint_name == "products_slug_key":
                raise DuplicateProductSlugError(product.slug) from exc
            raise

    async def get_by_id(self, product_id: UUID) -> Product | None:
        rows = await self._conn.fetch(_SELECT_BY_ID, product_id)
        if not rows:
            return None
        return _rows_to_product(rows)

    async def get_by_slug(self, slug: str) -> Product | None:
        rows = await self._conn.fetch(_SELECT_BY_SLUG, slug)
        if not rows:
            return None
        return _rows_to_product(rows)

    async def list_all(self) -> list[Product]:
        rows = await self._conn.fetch(_SELECT_ALL)
        return _rows_to_products(rows)

    async def update(self, product: Product) -> None:
        """One transaction: field edit, then per-variant upsert. `slug` is
        absent from the `SET` list -- frozen. `deleted_at` is never in the
        variant `SET` list either -- a replayed body can't resurrect a
        retired variant. Raises `ProductNotFoundError` if the product row
        is unknown or already retired (0 rows affected by the field
        `UPDATE`) -- checked BEFORE touching any variant, so an unknown/
        retired id fails atomically without side effects.
        """
        async with transaction(self._conn) as conn:
            result = await conn.execute(
                _UPDATE_PRODUCT_FIELDS,
                product.id,
                product.name,
                product.model,
                product.description,
                product.short_description,
            )
            if _rows_affected(result) == 0:
                raise ProductNotFoundError(product.id)
            if product.variants:
                await conn.executemany(
                    _UPSERT_VARIANT,
                    [
                        (variant.id, product.id, variant.color, variant.price, variant.cost)
                        for variant in product.variants
                    ],
                )

    async def soft_delete(self, product_id: UUID) -> None:
        result = await self._conn.execute(_SOFT_DELETE_PRODUCT, product_id)
        if _rows_affected(result) == 0:
            raise ProductNotFoundError(product_id)

    async def soft_delete_variant(self, product_id: UUID, variant_id: UUID) -> None:
        result = await self._conn.execute(
            _SOFT_DELETE_VARIANT, variant_id, product_id
        )
        if _rows_affected(result) == 0:
            raise VariantNotFoundError(variant_id, product_id)

    async def slug_exists(self, slug: str) -> bool:
        return await self._conn.fetchval(_SLUG_EXISTS, slug)
