"""`storage_path` derivation for product images.

See design.md Decision 2:
`{product_slug}/{color_slug|"hero"}-{image_id.hex[:12]}.webp` — a bare
`slug/color.ext` collides on multi-image-per-variant and on
delete-then-reupload (CDN caches the old object); the row-id-derived
suffix keeps the path traceable and unique while the color segment stays
purely cosmetic. Reuses `slug.slugify` rather than reimplementing
slugification — an unslugifiable color falls back to `"variant"`.
"""

from uuid import UUID

from gcell.products.application.exceptions import UnslugifiableProductNameError
from gcell.products.application.slug import slugify

_MAX_COLOR_SLUG_LENGTH = 40
_HERO_PREFIX = "hero"
_FALLBACK_COLOR_PREFIX = "variant"
_SUFFIX_LENGTH = 12
_EXTENSION = "webp"


def build_storage_path(product_slug: str, color: str | None, image_id: UUID) -> str:
    """Build the bucket-relative object path for a product image.

    `color` is `None` for a hero image (see admin-product-images spec
    "Hero Assignment Uses A Null Variant Id"). The client-supplied filename
    and mime type never reach this function or the resulting path — see
    the Threat Matrix's "Documentation-like paths" row.
    """
    prefix = _HERO_PREFIX if color is None else _color_prefix(color)
    suffix = image_id.hex[:_SUFFIX_LENGTH]
    return f"{product_slug}/{prefix}-{suffix}.{_EXTENSION}"


def _color_prefix(color: str) -> str:
    try:
        color_slug = slugify(color)
    except UnslugifiableProductNameError:
        return _FALLBACK_COLOR_PREFIX
    return color_slug[:_MAX_COLOR_SLUG_LENGTH].rstrip("-")
