"""Unit tests for `InMemoryProductImageRepository`.

No real DB -- exercises the same `ProductImageRepository` port contract as
`PostgresProductImageRepository` (`tests/integration/db/
test_product_image_repository.py`) with plain dicts, so upload/delete/
reorder use cases (Phase 4) can be tested without Postgres wiring.
"""

from uuid import uuid4

import pytest

from gcell.products.application.exceptions import ImageNotFoundError
from gcell.products.domain.product_image import ProductImage
from gcell.products.infrastructure.in_memory_product_image_repository import (
    InMemoryProductImageRepository,
)


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


async def test_add_then_get_by_id_round_trips_fields() -> None:
    repository = InMemoryProductImageRepository()
    image = make_image()

    await repository.add(image)
    fetched = await repository.get_by_id(image.id)

    assert fetched is not None
    assert fetched.id == image.id
    assert fetched.variant_id is None
    assert fetched.storage_path == image.storage_path


async def test_get_by_id_returns_none_for_unknown_id() -> None:
    repository = InMemoryProductImageRepository()

    assert await repository.get_by_id(uuid4()) is None


async def test_list_for_product_returns_only_that_products_images_sorted() -> None:
    repository = InMemoryProductImageRepository()
    product_id = uuid4()
    other_product_id = uuid4()
    first = make_image(product_id=product_id, sort_order=1)
    second = make_image(product_id=product_id, sort_order=0)
    other = make_image(product_id=other_product_id, sort_order=0)
    await repository.add(first)
    await repository.add(second)
    await repository.add(other)

    listed = await repository.list_for_product(product_id)

    assert [image.id for image in listed] == [second.id, first.id]


async def test_delete_is_a_hard_delete() -> None:
    repository = InMemoryProductImageRepository()
    image = make_image()
    await repository.add(image)

    await repository.delete(image.id)

    assert await repository.get_by_id(image.id) is None


async def test_delete_unknown_image_raises_image_not_found_error() -> None:
    repository = InMemoryProductImageRepository()

    with pytest.raises(ImageNotFoundError):
        await repository.delete(uuid4())


async def test_next_sort_order_is_independent_per_hero_and_variant_group() -> None:
    repository = InMemoryProductImageRepository()
    product_id = uuid4()
    variant_id = uuid4()

    assert await repository.next_sort_order(product_id, None) == 0
    assert await repository.next_sort_order(product_id, variant_id) == 0

    await repository.add(make_image(product_id=product_id, variant_id=None, sort_order=0))
    await repository.add(make_image(product_id=product_id, variant_id=variant_id, sort_order=0))
    await repository.add(make_image(product_id=product_id, variant_id=variant_id, sort_order=1))

    assert await repository.next_sort_order(product_id, None) == 1
    assert await repository.next_sort_order(product_id, variant_id) == 2


async def test_update_alt_text_changes_only_alt_text() -> None:
    repository = InMemoryProductImageRepository()
    image = make_image(alt_text="")
    await repository.add(image)

    await repository.update_alt_text(image.id, "A red case")

    updated = await repository.get_by_id(image.id)
    assert updated is not None
    assert updated.alt_text == "A red case"
    assert updated.storage_path == image.storage_path
    assert updated.sort_order == image.sort_order
    assert updated.variant_id == image.variant_id


async def test_update_alt_text_unknown_image_raises_image_not_found_error() -> None:
    repository = InMemoryProductImageRepository()

    with pytest.raises(ImageNotFoundError):
        await repository.update_alt_text(uuid4(), "whatever")


async def test_reorder_writes_sequential_sort_order_scoped_to_product() -> None:
    repository = InMemoryProductImageRepository()
    product_id = uuid4()
    first = make_image(product_id=product_id, sort_order=5)
    second = make_image(product_id=product_id, sort_order=9)
    third = make_image(product_id=product_id, sort_order=1)
    await repository.add(first)
    await repository.add(second)
    await repository.add(third)

    await repository.reorder(product_id, [third.id, first.id, second.id])

    listed = await repository.list_for_product(product_id)
    assert [image.id for image in listed] == [third.id, first.id, second.id]
    assert [image.sort_order for image in listed] == [0, 1, 2]
