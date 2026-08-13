"""Pure-domain unit tests for ProductImage.

No FastAPI, no Pydantic, no DB client is imported anywhere in this file or
in the module under test -- this test IS the hexagonal-boundary proof for
the new `product_image` domain module (see `test_domain_boundary.py` for
the AST-level enforcement).
"""

from uuid import uuid4

import pytest

from gcell.products.domain.product_image import (
    ALLOWED_UPLOAD_MIMES,
    MAX_UPLOAD_BYTES,
    ProductImage,
)


def make_image(**overrides: object) -> ProductImage:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "product_id": uuid4(),
        "variant_id": None,
        "storage_path": "iphone-13-funda/hero-abc123def456.webp",
        "alt_text": None,
        "sort_order": 0,
    }
    defaults.update(overrides)
    return ProductImage(**defaults)  # type: ignore[arg-type]


def test_product_image_with_valid_fields_is_constructed() -> None:
    image = make_image()

    assert image.variant_id is None
    assert image.sort_order == 0
    assert image.storage_path == "iphone-13-funda/hero-abc123def456.webp"


def test_product_image_may_be_assigned_to_a_variant() -> None:
    variant_id = uuid4()

    image = make_image(variant_id=variant_id)

    assert image.variant_id == variant_id


def test_product_image_storage_path_cannot_be_blank() -> None:
    with pytest.raises(ValueError):
        make_image(storage_path="   ")


def test_product_image_storage_path_cannot_be_empty_string() -> None:
    with pytest.raises(ValueError):
        make_image(storage_path="")


def test_product_image_sort_order_cannot_be_negative() -> None:
    with pytest.raises(ValueError):
        make_image(sort_order=-1)


def test_product_image_sort_order_zero_is_allowed() -> None:
    image = make_image(sort_order=0)

    assert image.sort_order == 0


def test_product_image_equality_is_id_based_not_value_based() -> None:
    shared_id = uuid4()
    first = make_image(id=shared_id, sort_order=0)
    second = make_image(id=shared_id, sort_order=5)

    assert first == second
    assert hash(first) == hash(second)


def test_product_image_with_distinct_ids_are_never_equal() -> None:
    first = make_image()
    second = make_image()

    assert first != second


def test_max_upload_bytes_is_five_mebibytes() -> None:
    assert MAX_UPLOAD_BYTES == 5 * 1024 * 1024


def test_allowed_upload_mimes_covers_jpeg_png_webp() -> None:
    assert ALLOWED_UPLOAD_MIMES == {"image/jpeg", "image/png", "image/webp"}
