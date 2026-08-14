"""Unit tests for `UploadProductImageUseCase`.

Fakes/spies only -- no real Storage or Postgres. Covers the sequence from
design.md's "Upload use-case sequence" (ownership before any Storage call,
size before normalize, compensation on insert failure) and the mandatory
exception reconciliation between `shared.application.image_normalizer`'s
`UnsupportedImageError`/`ImageTooLargeError` and the identically-named
`products.application.exceptions` classes (see that module's docstring).
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from gcell.products.application.exceptions import (
    ImageTooLargeError,
    ProductNotFoundError,
    UnsupportedImageError,
    VariantNotFoundError,
)
from gcell.products.domain.product import Product, ProductVariant
from gcell.products.domain.product_image import MAX_UPLOAD_BYTES
from gcell.products.infrastructure.in_memory_product_image_repository import (
    InMemoryProductImageRepository,
)
from gcell.products.infrastructure.in_memory_product_repository import (
    InMemoryProductRepository,
)
from gcell.shared.application.image_normalizer import (
    ImageTooLargeError as NormalizerImageTooLargeError,
)
from gcell.shared.application.image_normalizer import NormalizedImage
from gcell.shared.application.image_normalizer import (
    UnsupportedImageError as NormalizerUnsupportedImageError,
)


class FakeObjectStorage:
    def __init__(self) -> None:
        self.put_calls: list[tuple[str, bytes, str]] = []
        self.delete_calls: list[str] = []

    async def put(self, path: str, data: bytes, content_type: str) -> None:
        self.put_calls.append((path, data, content_type))

    async def delete(self, path: str) -> None:
        self.delete_calls.append(path)


class FakeImageNormalizer:
    def __init__(
        self, *, result: NormalizedImage | None = None, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.calls = 0

    def normalize(self, data: bytes) -> NormalizedImage:
        self.calls += 1
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


class RaisingImageRepository(InMemoryProductImageRepository):
    """Adds every image but raises on `add`, simulating an insert failure
    after the Storage object was already written."""

    def __init__(self, error: Exception) -> None:
        super().__init__()
        self._error = error

    async def add(self, image) -> None:  # type: ignore[override]
        raise self._error


def make_variant(color: str = "Negro") -> ProductVariant:
    return ProductVariant(
        id=uuid4(), color=color, price=Decimal("45000.00"), cost=Decimal("30000.00")
    )


async def make_persisted_product(
    repository: InMemoryProductRepository, *, variants: list[ProductVariant] | None = None
) -> Product:
    product = Product(
        id=uuid4(),
        slug=f"funda-iphone-15-{uuid4().hex[:8]}",
        name="Funda iPhone 15",
        model="Funda iPhone 15",
        variants=variants if variants is not None else [make_variant()],
    )
    await repository.add(product)
    return product


def make_normalized() -> NormalizedImage:
    return NormalizedImage(data=b"webp-bytes", content_type="image/webp", width=800, height=600)


def make_use_case(
    *,
    product_repository: InMemoryProductRepository | None = None,
    image_repository=None,
    object_storage: FakeObjectStorage | None = None,
    normalizer: FakeImageNormalizer | None = None,
):
    from gcell.products.application.upload_product_image import UploadProductImageUseCase

    return UploadProductImageUseCase(
        image_repository=image_repository or InMemoryProductImageRepository(),
        product_repository=product_repository or InMemoryProductRepository(),
        object_storage=object_storage or FakeObjectStorage(),
        normalizer=normalizer or FakeImageNormalizer(result=make_normalized()),
    )


async def test_upload_on_unknown_product_raises_product_not_found_before_any_storage_call() -> (
    None
):
    storage = FakeObjectStorage()
    use_case = make_use_case(object_storage=storage)

    with pytest.raises(ProductNotFoundError):
        await use_case.execute(
            product_id=uuid4(), data=b"x", variant_id=None, alt_text=None
        )

    assert storage.put_calls == []


async def test_upload_with_a_foreign_variant_id_raises_variant_not_found_before_storage() -> (
    None
):
    product_repository = InMemoryProductRepository()
    product = await make_persisted_product(product_repository)
    other_product = await make_persisted_product(product_repository)
    storage = FakeObjectStorage()
    use_case = make_use_case(product_repository=product_repository, object_storage=storage)

    with pytest.raises(VariantNotFoundError):
        await use_case.execute(
            product_id=product.id,
            data=b"x",
            variant_id=other_product.variants[0].id,
            alt_text=None,
        )

    assert storage.put_calls == []


async def test_oversized_file_raises_image_too_large_before_normalize_and_storage() -> None:
    product_repository = InMemoryProductRepository()
    product = await make_persisted_product(product_repository)
    storage = FakeObjectStorage()
    normalizer = FakeImageNormalizer(result=make_normalized())
    use_case = make_use_case(
        product_repository=product_repository, object_storage=storage, normalizer=normalizer
    )
    oversized_data = b"x" * (MAX_UPLOAD_BYTES + 1)

    with pytest.raises(ImageTooLargeError):
        await use_case.execute(
            product_id=product.id, data=oversized_data, variant_id=None, alt_text=None
        )

    assert normalizer.calls == 0
    assert storage.put_calls == []


async def test_normalizer_unsupported_image_error_is_reraised_as_the_products_exception() -> (
    None
):
    product_repository = InMemoryProductRepository()
    product = await make_persisted_product(product_repository)
    normalizer = FakeImageNormalizer(error=NormalizerUnsupportedImageError("bad format"))
    storage = FakeObjectStorage()
    use_case = make_use_case(
        product_repository=product_repository, object_storage=storage, normalizer=normalizer
    )

    with pytest.raises(UnsupportedImageError) as excinfo:
        await use_case.execute(
            product_id=product.id, data=b"not-an-image", variant_id=None, alt_text=None
        )

    assert excinfo.value.reason == "bad format"
    assert not isinstance(excinfo.value, NormalizerUnsupportedImageError)
    assert storage.put_calls == []


async def test_normalizer_image_too_large_error_is_reraised_as_the_products_exception() -> None:
    product_repository = InMemoryProductRepository()
    product = await make_persisted_product(product_repository)
    normalizer = FakeImageNormalizer(error=NormalizerImageTooLargeError(9_000_000, 5_000_000))
    storage = FakeObjectStorage()
    use_case = make_use_case(
        product_repository=product_repository, object_storage=storage, normalizer=normalizer
    )

    with pytest.raises(ImageTooLargeError) as excinfo:
        await use_case.execute(
            product_id=product.id, data=b"huge-image", variant_id=None, alt_text=None
        )

    assert excinfo.value.size_bytes == 9_000_000
    assert excinfo.value.max_bytes == 5_000_000
    assert storage.put_calls == []


async def test_db_insert_failure_triggers_exactly_one_compensating_delete_and_reraises() -> None:
    product_repository = InMemoryProductRepository()
    product = await make_persisted_product(product_repository)
    storage = FakeObjectStorage()
    original_error = RuntimeError("insert failed")
    image_repository = RaisingImageRepository(original_error)
    use_case = make_use_case(
        product_repository=product_repository,
        image_repository=image_repository,
        object_storage=storage,
    )

    with pytest.raises(RuntimeError) as excinfo:
        await use_case.execute(
            product_id=product.id, data=b"valid-bytes", variant_id=None, alt_text=None
        )

    assert excinfo.value is original_error
    assert len(storage.put_calls) == 1
    assert storage.delete_calls == [storage.put_calls[0][0]]


async def test_successful_upload_with_no_variant_persists_a_hero_image() -> None:
    product_repository = InMemoryProductRepository()
    product = await make_persisted_product(product_repository)
    image_repository = InMemoryProductImageRepository()
    storage = FakeObjectStorage()
    use_case = make_use_case(
        product_repository=product_repository,
        image_repository=image_repository,
        object_storage=storage,
    )

    image = await use_case.execute(
        product_id=product.id, data=b"valid-bytes", variant_id=None, alt_text="alt"
    )

    assert image.variant_id is None
    assert image.product_id == product.id
    assert image.storage_path.startswith(f"{product.slug}/hero-")
    persisted = await image_repository.get_by_id(image.id)
    assert persisted is not None
    assert len(storage.put_calls) == 1
    assert storage.put_calls[0] == (image.storage_path, b"webp-bytes", "image/webp")
    assert storage.delete_calls == []


async def test_successful_upload_with_a_variant_persists_a_variant_image() -> None:
    product_repository = InMemoryProductRepository()
    variant = make_variant("Rojo")
    product = await make_persisted_product(product_repository, variants=[variant])
    image_repository = InMemoryProductImageRepository()
    use_case = make_use_case(
        product_repository=product_repository, image_repository=image_repository
    )

    image = await use_case.execute(
        product_id=product.id, data=b"valid-bytes", variant_id=variant.id, alt_text=None
    )

    assert image.variant_id == variant.id
    assert image.storage_path.startswith(f"{product.slug}/rojo-")
