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

from gcell.products.application.exceptions import DuplicateProductSlugError
from gcell.products.domain.product import Product, ProductVariant
from gcell.shared.infrastructure.postgres import transaction

_SELECT_COLUMNS = """
    p.id, p.slug, p.name, p.model,
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
    INSERT INTO products (id, slug, name, model) VALUES ($1, $2, $3, $4)
"""

_INSERT_VARIANT = """
    INSERT INTO product_variants (id, product_id, color, price, cost)
    VALUES ($1, $2, $3, $4, $5)
"""


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
