"""Unit tests for `ProductsContextReader` (design.md DD2).

Exercises the adapter against the in-memory `products` repositories --
DD2's own testing-strategy line ("`photo_context` returns `None` for
another product's image id and for an unknown id | In-memory
products/image repositories"). The cross-parent-image-id case is this
PR's IDOR guard (Threat-Matrix "IDOR" row): `photo_context` resolves
`image_id` only through `list_for_product(product_id)`, so ownership is a
consequence of a product-scoped query, never a re-implemented predicate.
"""

import dataclasses
from uuid import uuid4

from gcell.content.application.product_context_reader import ProductCopyContext
from gcell.content.infrastructure.products_context_reader import (
    ProductsContextReader,
)
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.domain.product_image import ProductImage
from gcell.products.infrastructure.in_memory_product_image_repository import (
    InMemoryProductImageRepository,
)
from gcell.products.infrastructure.in_memory_product_repository import (
    InMemoryProductRepository,
)


def make_variant(**overrides: object) -> ProductVariant:
    from decimal import Decimal

    defaults: dict[str, object] = {
        "id": uuid4(),
        "color": "Negro",
        "price": Decimal("100.00"),
        "cost": Decimal("50.00"),
    }
    defaults.update(overrides)
    return ProductVariant(**defaults)  # type: ignore[arg-type]


def make_product(**overrides: object) -> Product:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "slug": f"funda-{uuid4().hex[:8]}",
        "name": "Funda Antigolpe",
        "model": "FA-100",
        "variants": [],
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


def make_reader(
    *, product_repository=None, image_repository=None
) -> ProductsContextReader:
    return ProductsContextReader(
        product_repository=product_repository or InMemoryProductRepository(),
        image_repository=image_repository or InMemoryProductImageRepository(),
    )


class TestProductContext:
    async def test_returns_context_with_name_model_and_variant_colors(self) -> None:
        product_repository = InMemoryProductRepository()
        variant_a = make_variant(color="Negro")
        variant_b = make_variant(color="Azul")
        product = make_product(
            name="Funda Antigolpe", model="FA-100", variants=[variant_a, variant_b]
        )
        await product_repository.add(product)
        reader = make_reader(product_repository=product_repository)

        context = await reader.product_context(product.id)

        assert context == ProductCopyContext(
            name="Funda Antigolpe", model="FA-100", colors=["Negro", "Azul"]
        )

    async def test_returns_none_for_unknown_product_id(self) -> None:
        reader = make_reader()

        context = await reader.product_context(uuid4())

        assert context is None

    def test_dto_has_no_price_or_cost_field(self) -> None:
        """OQ2 made structural: `ProductCopyContext` cannot carry a price
        because the field does not exist on the dataclass at all."""
        field_names = {f.name for f in dataclasses.fields(ProductCopyContext)}

        assert "price" not in field_names
        assert "cost" not in field_names
        assert field_names == {"name", "model", "colors"}


class TestPhotoContext:
    async def test_returns_context_for_an_owned_image(self) -> None:
        product_repository = InMemoryProductRepository()
        image_repository = InMemoryProductImageRepository()
        variant = make_variant(color="Rojo")
        product = make_product(
            name="Funda Antigolpe", model="FA-100", variants=[variant]
        )
        await product_repository.add(product)
        image = make_image(
            product_id=product.id,
            variant_id=variant.id,
            storage_path="funda/rojo-1.webp",
        )
        await image_repository.add(image)
        reader = make_reader(
            product_repository=product_repository, image_repository=image_repository
        )

        context = await reader.photo_context(product.id, image.id)

        assert context is not None
        assert context.storage_path == "funda/rojo-1.webp"
        assert context.product_name == "Funda Antigolpe"
        assert context.product_model == "FA-100"
        assert context.variant_color == "Rojo"

    async def test_returns_none_variant_color_for_a_hero_image(self) -> None:
        product_repository = InMemoryProductRepository()
        image_repository = InMemoryProductImageRepository()
        product = make_product()
        await product_repository.add(product)
        image = make_image(product_id=product.id, variant_id=None)
        await image_repository.add(image)
        reader = make_reader(
            product_repository=product_repository, image_repository=image_repository
        )

        context = await reader.photo_context(product.id, image.id)

        assert context is not None
        assert context.variant_color is None

    async def test_returns_none_for_an_unknown_image_id(self) -> None:
        product_repository = InMemoryProductRepository()
        product = make_product()
        await product_repository.add(product)
        reader = make_reader(product_repository=product_repository)

        context = await reader.photo_context(product.id, uuid4())

        assert context is None

    async def test_returns_none_for_another_products_image_id(self) -> None:
        """Threat-Matrix IDOR row: an image belonging to product B must
        never resolve when queried scoped to product A."""
        product_repository = InMemoryProductRepository()
        image_repository = InMemoryProductImageRepository()
        product_a = make_product(name="Producto A")
        product_b = make_product(name="Producto B")
        await product_repository.add(product_a)
        await product_repository.add(product_b)
        image_of_b = make_image(product_id=product_b.id)
        await image_repository.add(image_of_b)
        reader = make_reader(
            product_repository=product_repository, image_repository=image_repository
        )

        context = await reader.photo_context(product_a.id, image_of_b.id)

        assert context is None

    async def test_returns_none_for_unknown_product_id(self) -> None:
        image_repository = InMemoryProductImageRepository()
        image = make_image()
        await image_repository.add(image)
        reader = make_reader(image_repository=image_repository)

        context = await reader.photo_context(uuid4(), image.id)

        assert context is None
