"""Unit tests for `products/application/image_path.py`.

`build_storage_path` reuses `slug.slugify` for the colour segment instead
of reimplementing slugification -- see design.md Decision 2 (storage_path
format, 40-char colour truncation, unslugifiable-colour fallback to
"variant") and the product-media-storage spec "Storage Path Follows The
Seed Convention With A Uniqueness Suffix".
"""

import re
from uuid import UUID

from gcell.products.application.image_path import build_storage_path

_IMAGE_ID = UUID("11111111-2222-3333-4444-555555555555")


def test_hero_image_uses_hero_prefix() -> None:
    path = build_storage_path("iphone-13-funda", None, _IMAGE_ID)

    assert path == f"iphone-13-funda/hero-{_IMAGE_ID.hex[:12]}.webp"


def test_variant_image_uses_slugified_color_prefix() -> None:
    path = build_storage_path("iphone-13-funda", "Rojo Oscuro", _IMAGE_ID)

    assert path == f"iphone-13-funda/rojo-oscuro-{_IMAGE_ID.hex[:12]}.webp"


def test_storage_path_shape_matches_convention() -> None:
    path = build_storage_path("iphone-13-funda", "Negro", _IMAGE_ID)

    assert re.match(r"^iphone-13-funda/negro-[0-9a-f]{12}\.webp$", path)


def test_path_always_ends_in_webp_extension_regardless_of_color() -> None:
    path = build_storage_path("iphone-13-funda", "Negro", _IMAGE_ID)

    assert path.endswith(".webp")


def test_two_images_for_the_same_product_and_color_never_collide() -> None:
    first = build_storage_path(
        "iphone-13-funda", "Negro", UUID("11111111-1111-1111-1111-111111111111")
    )
    second = build_storage_path(
        "iphone-13-funda", "Negro", UUID("22222222-2222-2222-2222-222222222222")
    )

    assert first != second


def test_unslugifiable_color_falls_back_to_variant_prefix() -> None:
    path = build_storage_path("iphone-13-funda", "\U0001f381\U0001f381", _IMAGE_ID)

    assert path == f"iphone-13-funda/variant-{_IMAGE_ID.hex[:12]}.webp"


def test_color_slug_is_truncated_to_forty_characters() -> None:
    from gcell.products.application.slug import slugify

    long_color = "word " * 20  # slugifies far past 40 chars

    path = build_storage_path("iphone-13-funda", long_color, _IMAGE_ID)

    expected_prefix = slugify(long_color)[:40].rstrip("-")
    assert path == f"iphone-13-funda/{expected_prefix}-{_IMAGE_ID.hex[:12]}.webp"
    assert len(expected_prefix) <= 40
