"""Pure-domain unit tests for the products domain.

No FastAPI, no Pydantic, no DB client is imported anywhere in this file or
in the module under test — this test IS the hexagonal-boundary proof for
the products domain.
"""

import pytest

from gcell.products.domain.product import Product, ProductVariant


def make_variant(**overrides: object) -> ProductVariant:
    defaults: dict[str, object] = {
        "phone_model": "iPhone 13",
        "price": 45000.0,
        "cost": 30000.0,
    }
    defaults.update(overrides)
    return ProductVariant(**defaults)  # type: ignore[arg-type]


def test_product_with_valid_variant_is_constructed() -> None:
    variant = make_variant()
    product = Product(name="Funda transparente", variants=[variant])

    assert product.name == "Funda transparente"
    assert product.variants == [variant]


def test_product_name_cannot_be_blank() -> None:
    with pytest.raises(ValueError):
        Product(name="   ", variants=[make_variant()])


def test_variant_requires_a_phone_model() -> None:
    with pytest.raises(ValueError):
        make_variant(phone_model="")


def test_variant_price_cannot_be_negative() -> None:
    with pytest.raises(ValueError):
        make_variant(price=-1.0)


def test_variant_cost_cannot_be_negative() -> None:
    with pytest.raises(ValueError):
        make_variant(cost=-1.0)
