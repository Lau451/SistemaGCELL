"""Pure domain types for the `ai` domain.

`ai` is a leaf domain (D9 / DD5: `ai: set()` in `ALLOWED_EDGES`) -- nothing
here may import `httpx`, `fastapi`, or any other framework/infrastructure
package (see `test_domain_boundary.py`). `ai/application/content_generator.py`
is the domain-agnostic port that consumes `ImagePart`; the Gemini `httpx`
adapter (`ai/infrastructure/gemini_content_generator.py`, PR 7) is the only
place `SUPPORTED_IMAGE_MIMES` and `ImagePart` get turned into an actual
`inline_data` request part.
"""

from dataclasses import dataclass

# Mirrors `products/domain/product_image.py`'s `ALLOWED_UPLOAD_MIMES` --
# every stored product image is normalized to WebP on upload
# (`shared/infrastructure/pillow_image_normalizer.py`'s `_OUTPUT_CONTENT_TYPE`),
# but `ai/domain/` stays product-agnostic and simply mirrors the same
# input-format allowlist Gemini's `inline_data.mime_type` accepts.
SUPPORTED_IMAGE_MIMES = frozenset({"image/jpeg", "image/png", "image/webp"})


@dataclass(frozen=True)
class ImagePart:
    """One image attached to a generation call (Gemini `inline_data`).

    `mime_type` is expected to be one of `SUPPORTED_IMAGE_MIMES` -- the
    caller (a `content/` use case, via `ObjectStorage.get`'s
    `StoredObject.content_type`) is responsible for that; this type stays
    a plain data holder with no validation logic of its own (domain
    purity -- no exception-raising business rule belongs here).
    """

    data: bytes
    mime_type: str
