"""Postgres adapter for `ProductImageRepository`.

Takes an `asyncpg.Connection` (never a `Pool`) -- same pattern as
`PostgresProductRepository`/`PostgresStockMovementRepository`, so the
caller always controls the transaction boundary via
`shared.infrastructure.postgres.transaction()`.

`product_images` already exists (migration
`20260810000449_products_catalog.sql`) -- this adapter writes no
migration, only SQL against the shipped schema.

`delete` is a genuine HARD `DELETE FROM product_images`, in deliberate
contrast with the soft-delete used for products/variants -- images have
no order-integrity concern (see proposal.md decision 2). Zero rows
affected raises `ImageNotFoundError` with no `product_id` (a failed
delete-by-id alone cannot know which product an unknown/already-deleted
image belonged to).

`list_for_product` mirrors the `catalog_product_images` view's read-time
filter (see `supabase/migrations/20260811000000_products_soft_delete.sql`):
a soft-deleted variant's images stay in the table -- the composite FK does
not cascade on an `UPDATE` -- but must not be listed (design.md
"list_for_product joins product_variants ... AND deleted_at IS NULL").
"""

from uuid import UUID

import asyncpg

from gcell.products.application.exceptions import ImageNotFoundError
from gcell.products.domain.product_image import ProductImage
from gcell.shared.infrastructure.postgres import transaction

_SELECT_COLUMNS = "id, product_id, variant_id, storage_path, alt_text, sort_order"

_INSERT_IMAGE = f"""
    INSERT INTO product_images ({_SELECT_COLUMNS})
    VALUES ($1, $2, $3, $4, $5, $6)
"""

_SELECT_BY_ID = f"""
    SELECT {_SELECT_COLUMNS} FROM product_images WHERE id = $1
"""

_LIST_FOR_PRODUCT = """
    SELECT i.id, i.product_id, i.variant_id, i.storage_path, i.alt_text, i.sort_order
    FROM product_images i
    WHERE i.product_id = $1
      AND (
        i.variant_id IS NULL
        OR EXISTS (
          SELECT 1 FROM product_variants v
          WHERE v.id = i.variant_id AND v.deleted_at IS NULL
        )
      )
    ORDER BY i.sort_order, i.id
"""

_DELETE_IMAGE = "DELETE FROM product_images WHERE id = $1"

_NEXT_SORT_ORDER = """
    SELECT COALESCE(MAX(sort_order) + 1, 0)
    FROM product_images
    WHERE product_id = $1 AND variant_id IS NOT DISTINCT FROM $2
"""

_UPDATE_SORT_ORDER = """
    UPDATE product_images SET sort_order = $1 WHERE id = $2 AND product_id = $3
"""


def _rows_affected(command_tag: str) -> int:
    """asyncpg's `execute()` returns a command tag like `"DELETE 1"` --
    parse the trailing row count."""
    return int(command_tag.rsplit(" ", 1)[-1])


def _row_to_image(row: asyncpg.Record) -> ProductImage:
    return ProductImage(
        id=row["id"],
        product_id=row["product_id"],
        variant_id=row["variant_id"],
        storage_path=row["storage_path"],
        alt_text=row["alt_text"],
        sort_order=row["sort_order"],
    )


class PostgresProductImageRepository:
    def __init__(self, conn: asyncpg.Connection) -> None:
        self._conn = conn

    async def add(self, image: ProductImage) -> None:
        # Wrapped in `transaction()` (a SAVEPOINT when nested inside a
        # test's `db_conn`) -- same reason as `PostgresProductRepository.
        # add()`: a constraint violation only rolls back this insert, not
        # a caller's already-open outer transaction.
        async with transaction(self._conn) as conn:
            await conn.execute(
                _INSERT_IMAGE,
                image.id,
                image.product_id,
                image.variant_id,
                image.storage_path,
                image.alt_text,
                image.sort_order,
            )

    async def get_by_id(self, image_id: UUID) -> ProductImage | None:
        row = await self._conn.fetchrow(_SELECT_BY_ID, image_id)
        if row is None:
            return None
        return _row_to_image(row)

    async def list_for_product(self, product_id: UUID) -> list[ProductImage]:
        rows = await self._conn.fetch(_LIST_FOR_PRODUCT, product_id)
        return [_row_to_image(row) for row in rows]

    async def delete(self, image_id: UUID) -> None:
        result = await self._conn.execute(_DELETE_IMAGE, image_id)
        if _rows_affected(result) == 0:
            raise ImageNotFoundError(image_id)

    async def next_sort_order(self, product_id: UUID, variant_id: UUID | None) -> int:
        return await self._conn.fetchval(_NEXT_SORT_ORDER, product_id, variant_id)

    async def reorder(self, product_id: UUID, ordered_image_ids: list[UUID]) -> None:
        async with transaction(self._conn) as conn:
            await conn.executemany(
                _UPDATE_SORT_ORDER,
                [
                    (sort_order, image_id, product_id)
                    for sort_order, image_id in enumerate(ordered_image_ids)
                ],
            )
