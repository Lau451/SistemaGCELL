"""Image normalization port.

Cross-domain capability port (design.md Decision 1) -- lives in
`shared/application/` for the same dependency-direction reason as
`ObjectStorage` (see that module's docstring). Zero framework imports;
Pillow is confined to `shared/infrastructure/pillow_image_normalizer.py`.

`UnsupportedImageError`/`ImageTooLargeError` below are deliberately their
OWN classes, not the identically-named classes in
`products/application/exceptions.py` (created in PR1). `shared/` must
never import from `products/` (see `object_storage.py`'s docstring and
`shared/infrastructure/postgres.py`), so a `shared/infrastructure/`
adapter cannot raise a `products/` exception type without inverting that
dependency. Reconciling/translating between the two sets (e.g. catching
these in the Phase 4 upload use case and re-raising the `products/`
equivalents) is a Phase 4 concern -- design.md's Pillow guardrail table
names the `products/` classes directly, which this file deviates from
for that reason; see apply-progress for the full note.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class NormalizedImage:
    """The result of normalizing an uploaded image: always WebP-encoded
    bytes ready for `ObjectStorage.put`, plus the metadata the upload use
    case needs (Phase 4) without re-decoding.
    """

    data: bytes
    content_type: str
    width: int
    height: int


class ImageNormalizer(Protocol):
    """Port implemented by `shared/infrastructure/pillow_image_normalizer.py`.

    See design.md's Pillow guardrail table for the full failure mapping
    this MUST enforce (decode bomb, spoofed format, animated frames,
    disallowed color mode, oversized input/output, truncated data).
    """

    def normalize(self, data: bytes) -> NormalizedImage: ...


class UnsupportedImageError(Exception):
    """Raised when uploaded bytes fail format/animation/color-mode/decode
    validation (see the Pillow guardrail table in design.md).
    """

    def __init__(self, reason: str) -> None:
        super().__init__(f"Unsupported image: {reason}")
        self.reason = reason


class ImageTooLargeError(Exception):
    """Raised when uploaded bytes (or the decoded pixel dimensions, or
    the re-encoded output) exceed the normalizer's size limits (see the
    Pillow guardrail table in design.md).
    """

    def __init__(self, size: int, max_size: int) -> None:
        super().__init__(f"Image size {size} exceeds the {max_size} limit")
        self.size = size
        self.max_size = max_size
