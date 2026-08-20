"""Adapter-parity test: `PostgresProductRepository` and
`InMemoryProductRepository` MUST round-trip `description`/`short_description`
identically for the same sequence of create/read/update operations (spec
`product-persistence` "In-memory and Postgres adapters agree on both
fields").

Mirrors `test_product_image_repository_adapter_parity.py`'s pattern -- no
equivalent product-level parity file existed before PR2, so this is a new
file, not an extension of one (deviation noted in apply-progress.md).
"""

from decimal import Decimal
from uuid import uuid4

from gcell.products.domain.product import Product, ProductVariant
from gcell.products.infrastructure.in_memory_product_repository import (
    InMemoryProductRepository,
)
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)


def make_product(**overrides: object) -> Product:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "slug": f"funda-parity-desc-{uuid4().hex[:8]}",
        "name": "Funda paridad",
        "model": "iPhone 13",
        "variants": [
            ProductVariant(
                id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
            )
        ],
        "description": "Descripcion larga original",
        "short_description": "Blurb original",
    }
    defaults.update(overrides)
    return Product(**defaults)  # type: ignore[arg-type]


async def test_description_fields_round_trip_identically_on_both_adapters(
    db_conn,
) -> None:
    postgres_repository = PostgresProductRepository(db_conn)
    memory_repository = InMemoryProductRepository()

    for repository in (postgres_repository, memory_repository):
        product = make_product()
        await repository.add(product)

        fetched = await repository.get_by_id(product.id)
        assert fetched is not None
        assert fetched.description == "Descripcion larga original"
        assert fetched.short_description == "Blurb original"

        await repository.update(
            Product(
                id=product.id,
                slug=product.slug,
                name=product.name,
                model=product.model,
                variants=[],
                description=product.description,
                short_description="Blurb editado",
            )
        )

        updated = await repository.get_by_id(product.id)
        assert updated is not None
        assert updated.short_description == "Blurb editado"
        assert updated.description == "Descripcion larga original"


async def test_description_fields_default_to_none_on_both_adapters(db_conn) -> None:
    postgres_repository = PostgresProductRepository(db_conn)
    memory_repository = InMemoryProductRepository()

    for repository in (postgres_repository, memory_repository):
        product = make_product(
            slug=f"funda-parity-null-{uuid4().hex[:8]}",
            description=None,
            short_description=None,
        )
        await repository.add(product)

        fetched = await repository.get_by_id(product.id)
        assert fetched is not None
        assert fetched.description is None
        assert fetched.short_description is None
