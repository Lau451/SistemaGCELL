"""Unit test for `UnknownVariantError`'s message and carried `variant_id`."""

from uuid import uuid4

from gcell.stock.application.exceptions import UnknownVariantError


def test_unknown_variant_error_carries_the_offending_variant_id() -> None:
    variant_id = uuid4()

    error = UnknownVariantError(variant_id)

    assert error.variant_id == variant_id
    assert str(variant_id) in str(error)
