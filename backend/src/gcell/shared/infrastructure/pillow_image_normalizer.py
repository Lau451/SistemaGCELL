"""Pillow-backed `ImageNormalizer` adapter.

Confines Pillow to `shared/infrastructure/` -- `PIL` is in
`test_domain_boundary.py`'s `BANNED_MODULES`, so no `domain/` layer may
ever import it. Implements the full guardrail table from design.md
"Pillow safety guardrails":

- Decode bomb / oversized dimensions: `Image.MAX_IMAGE_PIXELS` PLUS an
  explicit pre-decode check of `im.size` against 40MP / 10,000px-per-side
  -- Pillow's own bomb guard only WARNS (never raises) between 1x and 2x
  the configured limit, so the explicit check is mandatory, not optional.
- Format allowlist by the DECODED `im.format` (`{JPEG, PNG, WEBP}`) --
  never a client-supplied `content_type`/filename (this port never
  receives either).
- Animated frame rejection (`n_frames > 1`).
- Color mode allowlist (`{RGB, RGBA, L, LA, P}`) -- rejects CMYK and
  other unsupported modes.
- `ImageFile.LOAD_TRUNCATED_IMAGES` stays at its default `False`, so a
  truncated file raises on `.load()` instead of silently partial-decoding.
- `ImageOps.exif_transpose()` first (bakes in orientation), then
  re-encodes WITHOUT an `exif=` kwarg -- strips all metadata including
  GPS.
- Always re-encodes to WebP, quality 82, long edge <= 1600px, downscale
  only (never upscale), alpha preserved.
- Input size checked BEFORE decode; output size re-asserted after encode.
"""

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

from gcell.shared.application.image_normalizer import (
    ImageNormalizer,
    ImageTooLargeError,
    NormalizedImage,
    UnsupportedImageError,
)

# Pillow's own decompression-bomb guard only WARNS (never raises) for
# anything below 2x this value -- see the module docstring above and
# design.md's guardrail table. The explicit checks below are what
# actually enforce the limit in the 1x-2x range.
Image.MAX_IMAGE_PIXELS = 40_000_000

_MAX_PIXELS = 40_000_000
_MAX_SIDE_PX = 10_000
_MAX_BYTES = 5 * 1024 * 1024
_ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
_ALLOWED_MODES = {"RGB", "RGBA", "L", "LA", "P"}
_OUTPUT_LONG_EDGE = 1600
_OUTPUT_QUALITY = 82
_OUTPUT_CONTENT_TYPE = "image/webp"


class PillowImageNormalizer(ImageNormalizer):
    """The only production `ImageNormalizer`; Pillow never leaves this
    file (see module docstring).
    """

    def normalize(self, data: bytes) -> NormalizedImage:
        if len(data) > _MAX_BYTES:
            raise ImageTooLargeError(len(data), _MAX_BYTES)

        try:
            im = Image.open(BytesIO(data))
        except UnidentifiedImageError:
            raise UnsupportedImageError("could not decode image") from None
        except Image.DecompressionBombError:
            # Only reachable for input > 2x MAX_IMAGE_PIXELS -- the 1x-2x
            # "warn only" range is caught explicitly below instead.
            raise ImageTooLargeError(-1, _MAX_PIXELS) from None

        width, height = im.size
        if width * height > _MAX_PIXELS or width > _MAX_SIDE_PX or height > _MAX_SIDE_PX:
            raise ImageTooLargeError(width * height, _MAX_PIXELS)

        if im.format not in _ALLOWED_FORMATS:
            raise UnsupportedImageError(f"unsupported format: {im.format}")

        if getattr(im, "n_frames", 1) > 1:
            raise UnsupportedImageError("animated images are not supported")

        if im.mode not in _ALLOWED_MODES:
            raise UnsupportedImageError(f"unsupported color mode: {im.mode}")

        try:
            im.load()
        except OSError:
            raise UnsupportedImageError("truncated or corrupt image data") from None

        im = ImageOps.exif_transpose(im) or im

        long_edge = max(im.size)
        if long_edge > _OUTPUT_LONG_EDGE:
            scale = _OUTPUT_LONG_EDGE / long_edge
            new_size = (
                max(1, round(im.width * scale)),
                max(1, round(im.height * scale)),
            )
            im = im.resize(new_size, Image.Resampling.LANCZOS)

        out = BytesIO()
        # No `exif=` kwarg -- this is what strips metadata (design.md
        # Decision: "re-encode WITHOUT passing exif").
        im.save(out, format="WEBP", quality=_OUTPUT_QUALITY)
        encoded = out.getvalue()

        if len(encoded) > _MAX_BYTES:
            raise ImageTooLargeError(len(encoded), _MAX_BYTES)

        return NormalizedImage(
            data=encoded,
            content_type=_OUTPUT_CONTENT_TYPE,
            width=im.width,
            height=im.height,
        )
