"""Unit tests for `ReorderProductImageUseCase`.

The submitted list must be EXACTLY a permutation of the product's own
image ids (design.md Decision 6): a foreign id, a repeated id, or an
omitted id must all be rejected as not-found with zero writes, scoped by
a set comparison against an already-fetched, product-scoped list -- never
a SQL join or a partial update.
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


def make_use_case(image_repository: InMemoryProductImageRepository):
    from gcell.products.application.reorder_product_image import ReorderProductImageUseCase

    return ReorderProductImageUseCase(image_repository=image_repository)


async def test_reorder_persists_the_new_sequence() -> None:
    image_repository = InMemoryProductImageRepository()
    product_id = uuid4()
    first = make_image(product_id=product_id, sort_order=0)
    second = make_image(product_id=product_id, sort_order=1)
    third = make_image(product_id=product_id, sort_order=2)
    for image in (first, second, third):
        await image_repository.add(image)
    use_case = make_use_case(image_repository)

    reordered = await use_case.execute(
        product_id=product_id, ordered_image_ids=[third.id, first.id, second.id]
    )

    assert [image.id for image in reordered] == [third.id, first.id, second.id]
    assert [image.sort_order for image in reordered] == [0, 1, 2]


async def test_reorder_list_containing_a_foreign_image_id_is_rejected_with_zero_writes() -> (
    None
):
    image_repository = InMemoryProductImageRepository()
    product_a = uuid4()
    product_b = uuid4()
    first = make_image(product_id=product_a, sort_order=0)
    second = make_image(product_id=product_a, sort_order=1)
    foreign = make_image(product_id=product_b, sort_order=0)
    for image in (first, second, foreign):
        await image_repository.add(image)
    use_case = make_use_case(image_repository)

    with pytest.raises(ImageNotFoundError):
        await use_case.execute(
            product_id=product_a, ordered_image_ids=[first.id, foreign.id]
        )

    persisted = await image_repository.list_for_product(product_a)
    assert [image.sort_order for image in persisted] == [0, 1]


async def test_reorder_list_missing_one_of_the_products_images_is_rejected_with_zero_writes() -> (
    None
):
    image_repository = InMemoryProductImageRepository()
    product_id = uuid4()
    first = make_image(product_id=product_id, sort_order=0)
    second = make_image(product_id=product_id, sort_order=1)
    third = make_image(product_id=product_id, sort_order=2)
    for image in (first, second, third):
        await image_repository.add(image)
    use_case = make_use_case(image_repository)

    with pytest.raises(ImageNotFoundError):
        await use_case.execute(product_id=product_id, ordered_image_ids=[first.id, second.id])

    persisted = await image_repository.list_for_product(product_id)
    assert [image.sort_order for image in persisted] == [0, 1, 2]


async def test_reorder_list_with_a_repeated_id_is_rejected_with_zero_writes() -> None:
    image_repository = InMemoryProductImageRepository()
    product_id = uuid4()
    first = make_image(product_id=product_id, sort_order=0)
    second = make_image(product_id=product_id, sort_order=1)
    await image_repository.add(first)
    await image_repository.add(second)
    use_case = make_use_case(image_repository)

    with pytest.raises(ImageNotFoundError):
        await use_case.execute(
            product_id=product_id, ordered_image_ids=[first.id, first.id]
        )

    persisted = await image_repository.list_for_product(product_id)
    assert [image.sort_order for image in persisted] == [0, 1]
