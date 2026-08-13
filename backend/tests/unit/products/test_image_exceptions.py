"""Unit tests for the new image-related application exceptions.

Construction-only coverage: these exceptions carry no behavior beyond
message formatting and attribute storage. The use cases and routes that
raise them (upload/delete/reorder, `/admin` image endpoints) ship in later
PRs (Phase 4/5) -- see tasks.md.
"""

from uuid import uuid4

from gcell.products.application.exceptions import (
    ImageNotFoundError,
    ImageTooLargeError,
    UnsupportedImageError,
)


def test_image_not_found_error_carries_image_and_product_ids() -> None:
    image_id = uuid4()
    product_id = uuid4()

    error = ImageNotFoundError(image_id, product_id)

    assert error.image_id == image_id
    assert error.product_id == product_id
    assert str(image_id) in str(error)
    assert str(product_id) in str(error)


def test_unsupported_image_error_carries_reason() -> None:
    error = UnsupportedImageError("unsupported_animated_image")

    assert error.reason == "unsupported_animated_image"
    assert "unsupported_animated_image" in str(error)


def test_image_too_large_error_carries_sizes() -> None:
    error = ImageTooLargeError(size_bytes=6_000_000, max_bytes=5_242_880)

    assert error.size_bytes == 6_000_000
    assert error.max_bytes == 5_242_880
    assert "6000000" in str(error)
    assert "5242880" in str(error)
