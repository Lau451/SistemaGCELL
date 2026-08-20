"""Adapter-parity test: `PostgresProductImageRepository` and
`InMemoryProductImageRepository` MUST produce the same observable final
state for the same sequence of insert/reorder/delete operations (spec:
product-persistence "In-memory and Postgres adapters agree on image
operations").

Scoped to insert/reorder/delete only -- NOT the soft-deleted-variant
read-time filter, which is a Postgres-only, cross-table concern the
in-memory adapter has no visibility into (see `InMemoryProductImageRepository`
module docstring).
"""

from decimal import Decimal
from uuid import uuid4

from gcell.products.domain.product import Product, ProductVariant
from gcell.products.domain.product_image import ProductImage
from gcell.products.infrastructure.in_memory_product_image_repository import (
    InMemoryProductImageRepository,
)
from gcell.products.infrastructure.postgres_product_image_repository import (
    PostgresProductImageRepository,
)
from gcell.products.infrastructure.postgres_product_repository import (
    PostgresProductRepository,
)


def _snapshot(images: list[ProductImage]) -> list[tuple[object, object, object]]:
    return [(image.id, image.sort_order, image.variant_id) for image in images]


async def test_insert_reorder_delete_produce_same_final_state_on_both_adapters(
    db_conn,
) -> None:
    product = Product(
        id=uuid4(),
        slug=f"funda-parity-{uuid4().hex[:8]}",
        name="Funda paridad",
        model="iPhone 13",
        variants=[
            ProductVariant(
                id=uuid4(), color="Negro", price=Decimal("45000.00"), cost=Decimal("30000.00")
            )
        ],
    )
    await PostgresProductRepository(db_conn).add(product)
    variant_id = product.variants[0].id

    hero = ProductImage(
        id=uuid4(),
        product_id=product.id,
        variant_id=None,
        storage_path=f"funda-parity/hero-{uuid4().hex[:12]}.webp",
        alt_text=None,
        sort_order=0,
    )
    variant_first = ProductImage(
        id=uuid4(),
        product_id=product.id,
        variant_id=variant_id,
        storage_path=f"funda-parity/negro-{uuid4().hex[:12]}.webp",
        alt_text=None,
        sort_order=1,
    )
    variant_second = ProductImage(
        id=uuid4(),
        product_id=product.id,
        variant_id=variant_id,
        storage_path=f"funda-parity/negro-{uuid4().hex[:12]}.webp",
        alt_text=None,
        sort_order=2,
    )
    images = [hero, variant_first, variant_second]

    postgres_repository = PostgresProductImageRepository(db_conn)
    memory_repository = InMemoryProductImageRepository()

    for repository in (postgres_repository, memory_repository):
        for image in images:
            await repository.add(image)
        # Reorder: variant_second, hero, variant_first -- then hard-delete
        # variant_first (the new middle position).
        await repository.reorder(product.id, [variant_second.id, hero.id, variant_first.id])
        await repository.delete(variant_first.id)
        # update_alt_text (design.md DD3) -- extends the same round-trip
        # proof to the new port method.
        await repository.update_alt_text(hero.id, "Updated alt text")

    postgres_final = await postgres_repository.list_for_product(product.id)
    memory_final = await memory_repository.list_for_product(product.id)

    assert len(postgres_final) == 2
    assert _snapshot(postgres_final) == _snapshot(memory_final)

    postgres_hero = await postgres_repository.get_by_id(hero.id)
    memory_hero = await memory_repository.get_by_id(hero.id)
    assert postgres_hero is not None
    assert memory_hero is not None
    assert postgres_hero.alt_text == "Updated alt text"
    assert memory_hero.alt_text == "Updated alt text"
