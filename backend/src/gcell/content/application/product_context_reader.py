"""Read port for the `content` domain's product-context lookups (DD2).

Narrow and read-only on purpose -- see design.md DD2. `content` does NOT
depend on `products.application.repository.ProductRepository` directly
(the `stock -> products` precedent) because that would hand `content` both
write methods (violating D5's "no write side effect" as a structural fact,
not a review duty) and `ProductVariant.price`/`cost` (violating OQ2's
user-confirmed "never send price to Gemini" constraint). Instead, this port
exposes exactly the two read shapes the `content` use cases need, via DTOs
that structurally cannot carry a price.

The only implementation is the products-backed adapter in
`content/infrastructure/products_context_reader.py` (PR 8); this PR ships
the port and its DTOs only, wired to nothing yet.
"""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class ProductCopyContext:
    """Input for the generate-copy use case.

    NO price/cost field exists here -- OQ2 ("no price in the prompt") made
    structural: a caller cannot leak a price it was never handed, unlike a
    `Product` that carries `ProductVariant.price`/`cost` on every variant.
    """

    name: str
    model: str
    colors: list[str]


@dataclass(frozen=True)
class ProductPhotoContext:
    """Input for the generate-alt-text use case.

    `variant_color` is `None` for a hero image (`variant_id IS NULL`) --
    that is not an error state, mirrors `ProductImage.variant_id`'s own
    convention.
    """

    storage_path: str
    product_name: str
    product_model: str
    variant_color: str | None


class ProductContextReader(Protocol):
    """Port implemented by `content/infrastructure/products_context_reader.py`."""

    async def product_context(self, product_id: UUID) -> ProductCopyContext | None:
        """`None` = no active product with that id."""
        ...

    async def photo_context(
        self, product_id: UUID, image_id: UUID
    ) -> ProductPhotoContext | None:
        """`None` = unknown OR not owned by `product_id`.

        Resolved via `ProductImageRepository.list_for_product(product_id)`,
        so ownership is a *consequence* of a product-scoped query rather
        than a re-implemented predicate (design.md DD2) -- it inherits the
        soft-deleted-variant hiding for free. Callers/routes MUST map
        `None` to `404 not_found`, never `403` (Threat-Matrix IDOR row).
        """
        ...
