"""Repository port for the products domain.

Defined in `application/` (not `domain/`) because it is a boundary
contract the application layer depends on and infrastructure adapters
implement — the domain model itself has no notion of persistence.
"""

from typing import Protocol
from uuid import UUID

from gcell.products.domain.product import Product


class ProductRepository(Protocol):
    """Port implemented by infrastructure adapters (in-memory, DB, ...).

    Keyed by `slug` — the only DB-unique business identifier — not `name`.
    `get_by_name` does not exist: it would encourage lookups/duplicate
    checks against a non-unique field.
    """

    async def add(self, product: Product) -> None: ...

    async def get_by_id(self, product_id: UUID) -> Product | None: ...

    async def get_by_slug(self, slug: str) -> Product | None: ...

    async def list_all(self) -> list[Product]: ...

    async def update(self, product: Product) -> None:
        """Persist field edits and add/update the given variants, in ONE
        transaction. NEVER deletes or retires a variant. Raises
        `ProductNotFoundError` if no ACTIVE product with that id exists.
        `slug` is never accepted or altered -- it is frozen at creation.
        `update` now also persists `description` and `short_description` as
        full-replacement scalars, exactly like `name`/`model` -- a caller
        omitting either clears it (content-ai-domains PR2).
        """
        ...

    async def soft_delete(self, product_id: UUID) -> None:
        """Retire a product via `UPDATE` (never a `DELETE`), cascading to
        its variants at read time. Raises `ProductNotFoundError` if no
        ACTIVE product with that id exists.
        """
        ...

    async def soft_delete_variant(self, product_id: UUID, variant_id: UUID) -> None:
        """Retire a single variant of `product_id` via `UPDATE`. Raises
        `VariantNotFoundError` if the variant does not exist, does not
        belong to `product_id`, or is already retired -- never a `403` that
        would confirm cross-parent existence.
        """
        ...

    async def slug_exists(self, slug: str) -> bool:
        """Whether `slug` is already taken by ANY product. Ignores
        `deleted_at` ON PURPOSE -- mirrors the global unique index, so a
        retired product's slug is never handed to a different product.
        """
        ...
