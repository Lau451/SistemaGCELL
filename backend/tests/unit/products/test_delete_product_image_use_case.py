"""Unit tests for `DeleteProductImageUseCase`.

Row FIRST, then best-effort Storage delete -- the opposite order from
upload (design.md Decision 5). A non-404 `ObjectStorageError` on the
Storage delete must be swallowed once the row is gone; a `404` is already
handled as success by the `ObjectStorage` port contract itself.
"""

from uuid import uuid4

import pytest

from gcell.products.application.exceptions import ImageNotFoundError
from gcell.products.domain.product_image import ProductImage
from gcell.products.infrastructure.in_memory_product_image_repository import (
    InMemoryProductImageRepository,
)
from gcell.shared.application.object_storage import ObjectStorageError


class FakeObjectStorage:
    def __init__(self, *, raise_on_delete: Exception | None = None) -> None:
        self.delete_calls: list[str] = []
        self._raise_on_delete = raise_on_delete

    async def put(self, path: str, data: bytes, content_type: str) -> None:  # pragma: no cover
        raise AssertionError("delete use case must never call Storage.put")

    async def delete(self, path: str) -> None:
        self.delete_calls.append(path)
        if self._raise_on_delete is not None:
            raise self._raise_on_delete


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


def make_use_case(*, image_repository=None, object_storage=None):
    from gcell.products.application.delete_product_image import DeleteProductImageUseCase

    return DeleteProductImageUseCase(
        image_repository=image_repository or InMemoryProductImageRepository(),
        object_storage=object_storage or FakeObjectStorage(),
    )


async def test_deleting_an_unknown_image_raises_image_not_found() -> None:
    use_case = make_use_case()

    with pytest.raises(ImageNotFoundError):
        await use_case.execute(product_id=uuid4(), image_id=uuid4())


async def test_deleting_an_image_belonging_to_another_product_raises_image_not_found() -> (
    None
):
    image_repository = InMemoryProductImageRepository()
    image = make_image()
    await image_repository.add(image)
    use_case = make_use_case(image_repository=image_repository)

    with pytest.raises(ImageNotFoundError):
        await use_case.execute(product_id=uuid4(), image_id=image.id)

    # the row must survive an ownership rejection
    assert await image_repository.get_by_id(image.id) is not None


async def test_delete_removes_the_row_and_deletes_the_storage_object() -> None:
    image_repository = InMemoryProductImageRepository()
    image = make_image()
    await image_repository.add(image)
    storage = FakeObjectStorage()
    use_case = make_use_case(image_repository=image_repository, object_storage=storage)

    await use_case.execute(product_id=image.product_id, image_id=image.id)

    assert await image_repository.get_by_id(image.id) is None
    assert storage.delete_calls == [image.storage_path]


async def test_storage_delete_failure_is_swallowed_and_the_row_stays_deleted() -> None:
    image_repository = InMemoryProductImageRepository()
    image = make_image()
    await image_repository.add(image)
    storage = FakeObjectStorage(raise_on_delete=ObjectStorageError("boom"))
    use_case = make_use_case(image_repository=image_repository, object_storage=storage)

    await use_case.execute(product_id=image.product_id, image_id=image.id)  # no raise

    assert await image_repository.get_by_id(image.id) is None
    assert storage.delete_calls == [image.storage_path]
