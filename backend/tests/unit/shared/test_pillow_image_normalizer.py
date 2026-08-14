"""Guardrail suite for `PillowImageNormalizer` (design.md "Pillow safety
guardrails" table).

Every scenario here is a threat-matrix case: user-supplied bytes cross a
trust boundary before ever reaching Storage. Bytes are crafted directly
(never real network/Storage calls) -- see design.md's Testing section
("12001x12001 header rejected WITHOUT decode", etc).
"""

import io
import struct
import zlib

import pytest
from PIL import Image

from gcell.shared.application.image_normalizer import ImageTooLargeError, UnsupportedImageError
from gcell.shared.infrastructure.pillow_image_normalizer import PillowImageNormalizer


def _fake_png_header(width: int, height: int) -> bytes:
    """A syntactically valid PNG with only IHDR + IEND -- no pixel data.

    Lets us assert dimensions are rejected from the header alone, BEFORE
    any decode is attempted (a real `width x height` bitmap at these
    sizes would be a genuine decompression-bomb-scale allocation).
    """
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IEND", b"")


def _encode(im: Image.Image, fmt: str, **kwargs) -> bytes:
    buf = io.BytesIO()
    im.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


class TestDecodeBombAndOversized:
    def test_rejects_header_only_bytes_far_beyond_the_pixel_limit(self) -> None:
        # 40000x40000 = 1.6B pixels, tiny file (no IDAT) -- Pillow's own
        # `_decompression_bomb_check` inside `Image.open` would already
        # raise for this magnitude, proving rejection happens without
        # ever attempting to allocate/decode pixel data.
        data = _fake_png_header(40_000, 40_000)

        with pytest.raises(ImageTooLargeError):
            PillowImageNormalizer().normalize(data)

    def test_rejects_dimensions_in_the_1x_to_2x_warn_only_range(self) -> None:
        # 8000x7500 = 60,000,000 pixels: 1.5x our 40MP limit. Pillow's
        # built-in bomb guard only WARNS in this range (never raises) --
        # design.md is explicit this is why an EXPLICIT pre-decode check
        # is mandatory, not optional. This is the case that would slip
        # through without it.
        data = _fake_png_header(8_000, 7_500)

        with pytest.raises(ImageTooLargeError):
            PillowImageNormalizer().normalize(data)

    def test_rejects_a_real_valid_image_exceeding_the_per_side_limit(self) -> None:
        # A genuinely decodable, tiny (10001 x 1 px) image -- proves the
        # 10,000px/side check fires independently of the 40MP pixel-count
        # check (this image is nowhere near 40MP).
        im = Image.new("L", (10_001, 1), 128)
        data = _encode(im, "PNG")

        with pytest.raises(ImageTooLargeError):
            PillowImageNormalizer().normalize(data)


class TestFormatAllowlist:
    def test_rejects_a_decoded_format_outside_the_allowlist(self) -> None:
        # GIF decodes fine but is not in {JPEG, PNG, WEBP} -- classification
        # is by the DECODED format, never a client-supplied content_type
        # (normalize() never receives one).
        im = Image.new("RGB", (30, 30), (1, 2, 3))
        data = _encode(im, "GIF")

        with pytest.raises(UnsupportedImageError):
            PillowImageNormalizer().normalize(data)


class TestAnimatedRejection:
    def test_rejects_an_animated_webp(self) -> None:
        frames = [Image.new("RGB", (20, 20), (i * 10, 0, 0)) for i in range(3)]
        buf = io.BytesIO()
        frames[0].save(buf, format="WEBP", save_all=True, append_images=frames[1:])

        with pytest.raises(UnsupportedImageError):
            PillowImageNormalizer().normalize(buf.getvalue())


class TestColorModeAllowlist:
    def test_rejects_cmyk(self) -> None:
        im = Image.new("CMYK", (40, 40), (0, 0, 0, 0))
        data = _encode(im, "JPEG")

        with pytest.raises(UnsupportedImageError):
            PillowImageNormalizer().normalize(data)


class TestExifStripped:
    def test_strips_exif_metadata_from_the_normalized_output(self) -> None:
        im = Image.new("RGB", (300, 200), (10, 20, 30))
        exif = Image.Exif()
        exif[0x0112] = 1  # Orientation: normal (keep this test decode-simple)
        exif[0x9286] = "gps-and-serial-like-payload"
        data = _encode(im, "JPEG", exif=exif.tobytes())

        result = PillowImageNormalizer().normalize(data)

        reopened = Image.open(io.BytesIO(result.data))
        assert dict(reopened.getexif()) == {}


class TestNonImageBytes:
    def test_rejects_bytes_that_are_not_an_image_at_all(self) -> None:
        with pytest.raises(UnsupportedImageError):
            PillowImageNormalizer().normalize(b"not an image, just random bytes 1234567890")


class TestTruncatedFile:
    def test_rejects_a_truncated_jpeg(self) -> None:
        im = Image.new("RGB", (200, 200), (255, 0, 0))
        full = _encode(im, "JPEG", quality=90)
        truncated = full[: len(full) - 40]

        with pytest.raises(UnsupportedImageError):
            PillowImageNormalizer().normalize(truncated)


class TestResizeAndReencode:
    def test_downscales_a_4000px_image_to_at_most_1600px_webp(self) -> None:
        im = Image.new("RGB", (4000, 2000), (5, 100, 200))
        data = _encode(im, "PNG")

        result = PillowImageNormalizer().normalize(data)

        assert result.content_type == "image/webp"
        reopened = Image.open(io.BytesIO(result.data))
        assert reopened.format == "WEBP"
        assert max(reopened.size) <= 1600
        assert result.width == reopened.width
        assert result.height == reopened.height

    def test_never_upscales_a_small_image(self) -> None:
        im = Image.new("RGB", (100, 80), (5, 100, 200))
        data = _encode(im, "PNG")

        result = PillowImageNormalizer().normalize(data)

        assert result.width == 100
        assert result.height == 80

    def test_preserves_alpha_channel(self) -> None:
        im = Image.new("RGBA", (100, 80), (5, 100, 200, 128))
        data = _encode(im, "PNG")

        result = PillowImageNormalizer().normalize(data)

        reopened = Image.open(io.BytesIO(result.data))
        assert reopened.mode in {"RGBA", "P"}
        assert "A" in Image.open(io.BytesIO(result.data)).convert("RGBA").getbands()
