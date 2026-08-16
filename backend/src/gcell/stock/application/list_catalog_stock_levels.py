"""Use case: catalog-wide, per-variant stock triage list.

Owns the three rules a flat triage view needs (design.md Decision 1, exact
`ListVariantStockMovementsUseCase` precedent -- that use case owns its own
clamp for the same reason): the `below` clamp, the AND-combined
case-insensitive substring search, and the total ascending sort order.
Imports `ProductRepository`/`CatalogStockLevelsReader` ports only, so the
dependency direction stays `stock -> products` (D7, convention-only -- not
enforced by `test_domain_boundary.py`).

`below=0` is a valid, meaningful threshold ("only out-of-stock" -- D11): the
clamp is `max(0, below)`, NEVER `max(1, ...)` like the movements-limit
precedent uses. `search` never reaches SQL (Decision 4) -- matching is a
plain Python `in` over already-fetched, in-memory rows, so even an
adversarial, SQL-injection-shaped string is just an ordinary (typically
non-matching) substring.
"""

from dataclasses import dataclass
from uuid import UUID

from gcell.products.application.repository import ProductRepository
from gcell.stock.application.catalog_stock_levels_reader import CatalogStockLevelsReader


@dataclass(frozen=True)
class CatalogStockRow:
    product_id: UUID
    product_slug: str
    product_name: str
    product_model: str
    variant_id: UUID
    color: str
    quantity_on_hand: int


@dataclass
class ListCatalogStockLevelsUseCase:
    products: ProductRepository
    stock_levels: CatalogStockLevelsReader

    async def execute(
        self, below: int | None = None, search: str | None = None
    ) -> list[CatalogStockRow]:
        products = await self.products.list_all()
        variant_ids = [variant.id for product in products for variant in product.variants]
        quantities = await self.stock_levels.quantities_for_variants(variant_ids)

        rows = [
            CatalogStockRow(
                product_id=product.id,
                product_slug=product.slug,
                product_name=product.name,
                product_model=product.model,
                variant_id=variant.id,
                color=variant.color,
                quantity_on_hand=quantities[variant.id],
            )
            for product in products
            for variant in product.variants
        ]

        term = (search or "").strip().casefold()  # blank == no search (D8/D9)
        threshold = None if below is None else max(0, below)  # D5/D11, never max(1, ..)
        rows = [
            row
            for row in rows  # AND (D10)
            if (threshold is None or row.quantity_on_hand <= threshold)
            and (
                not term
                or term in row.product_name.casefold()
                or term in row.color.casefold()
            )
        ]
        rows.sort(
            key=lambda row: (
                row.quantity_on_hand,
                row.product_name.casefold(),
                row.color.casefold(),
                str(row.variant_id),
            )
        )  # total order
        return rows
