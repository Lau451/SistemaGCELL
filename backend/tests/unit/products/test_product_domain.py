"""Pure-domain unit tests for the products domain.

No FastAPI, no Pydantic, no DB client is imported anywhere in this file or
in the module under test — this test IS the hexagonal-boundary proof for
the products domain.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from gcell.products.domain.product import Product, ProductVariant


def make_variant(**overrides: object) -> ProductVariant:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "color": "Negro",
        "price": Decimal("45000.00"),
        "cost": Decimal("30000.00"),
    }
    defaults.update(overrides)
    return ProductVariant(**defaults)  # type: ignore[arg-type]


def make_product(**overrides: object) -> Product:
    defaults: dict[str, object] = {
        "id": uuid4(),
        "slug": "iphone-13-funda",
        "name": "Funda transparente",
        "model": "iPhone 13",
        "variants": [make_variant()],
    }
    defaults.update(overrides)
    return Product(**defaults)  # type: ignore[arg-type]


def test_product_with_valid_variant_is_constructed() -> None:
    variant = make_variant()
    product = make_product(variants=[variant])

    assert product.name == "Funda transparente"
    assert product.model == "iPhone 13"
    assert product.slug == "iphone-13-funda"
    assert product.variants == [variant]


def test_product_name_cannot_be_blank() -> None:
    with pytest.raises(ValueError):
        make_product(name="   ")


def test_product_model_cannot_be_blank() -> None:
    with pytest.raises(ValueError):
        make_product(model="")


def test_product_slug_must_be_lowercase_kebab_case() -> None:
    with pytest.raises(ValueError):
        make_product(slug="iPhone 13")


def test_product_slug_cannot_be_blank() -> None:
    with pytest.raises(ValueError):
        make_product(slug="")


def test_product_slug_cannot_exceed_eighty_characters() -> None:
    with pytest.raises(ValueError):
        make_product(slug="a" * 81)


def test_product_equality_is_id_based_not_value_based() -> None:
    shared_id = uuid4()
    first = make_product(id=shared_id, name="Funda A")
    second = make_product(id=shared_id, name="Funda B")

    assert first == second
    assert hash(first) == hash(second)


def test_product_with_distinct_ids_are_never_equal() -> None:
    first = make_product(name="Funda transparente")
    second = make_product(name="Funda transparente")

    assert first != second


def test_variant_requires_a_color() -> None:
    with pytest.raises(ValueError):
        make_variant(color="")


def test_variant_price_must_be_decimal_not_float() -> None:
    with pytest.raises(TypeError):
        make_variant(price=45000.0)


def test_variant_cost_must_be_decimal_not_float() -> None:
    with pytest.raises(TypeError):
        make_variant(cost=30000.0)


def test_variant_price_cannot_be_negative() -> None:
    with pytest.raises(ValueError):
        make_variant(price=Decimal("-1.00"))


def test_variant_cost_cannot_be_negative() -> None:
    with pytest.raises(ValueError):
        make_variant(cost=Decimal("-1.00"))


def test_variant_price_must_be_finite() -> None:
    with pytest.raises(ValueError):
        make_variant(price=Decimal("NaN"))


def test_variant_price_cannot_exceed_two_decimal_places() -> None:
    with pytest.raises(ValueError):
        make_variant(price=Decimal("45000.123"))


def test_variant_equality_is_id_based_not_value_based() -> None:
    shared_id = uuid4()
    first = make_variant(id=shared_id, color="Negro")
    second = make_variant(id=shared_id, color="Rojo")

    assert first == second
    assert hash(first) == hash(second)


def test_variant_with_distinct_ids_are_never_equal() -> None:
    first = make_variant(color="Negro")
    second = make_variant(color="Negro")

    assert first != second


def test_product_description_fields_default_to_none() -> None:
    product = make_product()

    assert product.description is None
    assert product.short_description is None


def test_product_description_fields_can_be_set() -> None:
    product = make_product(
        description="Funda de silicona transparente antigolpes",
        short_description="Funda transparente",
    )

    assert product.description == "Funda de silicona transparente antigolpes"
    assert product.short_description == "Funda transparente"
