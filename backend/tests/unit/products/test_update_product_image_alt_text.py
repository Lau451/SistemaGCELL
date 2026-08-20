"""Unit tests for `UpdateProductImageAltTextUseCase` (design.md DD3).

Reuses the exact ownership-guard shape already proven by
`DeleteProductImageUseCase`/`ReorderProductImageUseCase`: `get_by_id` ->
`image is None or image.product_id != product_id` -> `ImageNotFoundError`,
never a 403 that would confirm a cross-parent image's existence (spec
admin-product-images "Alt-text update on another product's image is
rejected", design's Threat-Matrix IDOR row).
"""

from uuid import uuid4

import pytest

from gcell.products.application.exceptions import ImageNotFoundError
from gcell.products.application.update_product_image_alt_text import (
    UpdateProductImageAltTextUseCase,
)
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
        "alt_text": "",
        "sort_order": 0,
    }
    defaults.update(overrides)
    return ProductImage(**defaults)  # type: ignore[arg-type]


def make_use_case(*, image_repository=None):
    return UpdateProductImageAltTextUseCase(
        image_repository=image_repository or InMemoryProductImageRepository(),
    )


async def test_updates_alt_text_and_changes_no_other_field() -> None:
    image_repository = InMemoryProductImageRepository()
    image = make_image(alt_text="")
    await image_repository.add(image)
    use_case = make_use_case(image_repository=image_repository)

    updated = await use_case.execute(
        product_id=image.product_id, image_id=image.id, alt_text="A red case"
    )

    assert updated.alt_text == "A red case"
    assert updated.id == image.id
    assert updated.product_id == image.product_id
    assert updated.variant_id == image.variant_id
    assert updated.storage_path == image.storage_path
    assert updated.sort_order == image.sort_order

    persisted = await image_repository.get_by_id(image.id)
    assert persisted is not None
    assert persisted.alt_text == "A red case"
    assert persisted.storage_path == image.storage_path
    assert persisted.sort_order == image.sort_order


async def test_non_blank_alt_text_is_stored_stripped() -> None:
    image_repository = InMemoryProductImageRepository()
    image = make_image(alt_text="")
    await image_repository.add(image)
    use_case = make_use_case(image_repository=image_repository)

    updated = await use_case.execute(
        product_id=image.product_id, image_id=image.id, alt_text="  A red case  "
    )

    assert updated.alt_text == "A red case"


async def test_null_alt_text_clears_the_column() -> None:
    image_repository = InMemoryProductImageRepository()
    image = make_image(alt_text="An old description")
    await image_repository.add(image)
    use_case = make_use_case(image_repository=image_repository)

    updated = await use_case.execute(
        product_id=image.product_id, image_id=image.id, alt_text=None
    )

    assert updated.alt_text is None
    persisted = await image_repository.get_by_id(image.id)
    assert persisted is not None
    assert persisted.alt_text is None


async def test_blank_after_strip_alt_text_clears_the_column() -> None:
    image_repository = InMemoryProductImageRepository()
    image = make_image(alt_text="An old description")
    await image_repository.add(image)
    use_case = make_use_case(image_repository=image_repository)

    updated = await use_case.execute(
        product_id=image.product_id, image_id=image.id, alt_text="   "
    )

    assert updated.alt_text is None


async def test_unknown_image_id_raises_image_not_found() -> None:
    use_case = make_use_case()

    with pytest.raises(ImageNotFoundError):
        await use_case.execute(
            product_id=uuid4(), image_id=uuid4(), alt_text="whatever"
        )


async def test_cross_parent_image_id_raises_image_not_found_and_leaves_alt_text_unchanged() -> (
    None
):
    """spec admin-product-images "Alt-text update on another product's
    image is rejected" -- product A referencing product B's image must
    404, never mutate either image's `alt_text`.
    """
    image_repository = InMemoryProductImageRepository()
    product_a_id = uuid4()
    image_of_b = make_image(product_id=uuid4(), alt_text="Belongs to B")
    await image_repository.add(image_of_b)
    use_case = make_use_case(image_repository=image_repository)

    with pytest.raises(ImageNotFoundError):
        await use_case.execute(
            product_id=product_a_id, image_id=image_of_b.id, alt_text="Hijacked"
        )

    persisted = await image_repository.get_by_id(image_of_b.id)
    assert persisted is not None
    assert persisted.alt_text == "Belongs to B"
