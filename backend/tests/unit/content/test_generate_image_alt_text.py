"""Unit tests for `GenerateImageAltTextUseCase` (design.md's Sequence
Diagram "Generate alt text (image input, DD1)" + admin-ai-content-authoring
spec "Generate Alt Text Is A Separate, Image-Input Action").

Fakes only -- `FakeContentGenerator` (mirrors `ContentGenerator`),
`FakeProductContextReader` (mirrors `ProductContextReader`), and
`FakeObjectStorage` (mirrors `ObjectStorage`). Unlike
`GenerateProductCopyUseCase`, this use case has no products-repository
"no price" test to mirror -- `ProductPhotoContext` (PR 8's DD2 DTO)
structurally has no price/cost field, same reasoning already proven for
`ProductCopyContext`.
"""

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

import pytest

from gcell.ai.application.content_generator import GenerationError
from gcell.ai.domain.generation import ImagePart
from gcell.content.application.generate_image_alt_text import (
    GenerateImageAltTextUseCase,
)
from gcell.content.application.product_context_reader import ProductPhotoContext
from gcell.content.domain.copy_draft import ALT_TEXT_CAP, AltTextDraft
from gcell.products.application.exceptions import ImageNotFoundError
from gcell.shared.application.object_storage import ObjectStorageError, StoredObject


class FakeContentGenerator:
    def __init__(
        self, *, result: dict[str, Any] | None = None, error: Exception | None = None
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def generate_json(
        self,
        *,
        instruction: str,
        response_schema: dict[str, Any],
        image: Any = None,
        max_output_tokens: int = 1024,
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "instruction": instruction,
                "response_schema": response_schema,
                "image": image,
                "max_output_tokens": max_output_tokens,
            }
        )
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


@dataclass
class FakeProductContextReader:
    photo: ProductPhotoContext | None

    async def product_context(self, product_id: object) -> None:
        raise NotImplementedError("not used by GenerateImageAltTextUseCase")

    async def photo_context(
        self, product_id: object, image_id: object
    ) -> ProductPhotoContext | None:
        return self.photo


class FakeObjectStorage:
    def __init__(
        self, *, stored: StoredObject | None = None, error: Exception | None = None
    ) -> None:
        self.stored = stored
        self.error = error
        self.get_calls: list[str] = []

    async def put(self, path: str, data: bytes, content_type: str) -> None:
        raise NotImplementedError("not used by GenerateImageAltTextUseCase")

    async def get(self, path: str) -> StoredObject:
        self.get_calls.append(path)
        if self.error is not None:
            raise self.error
        assert self.stored is not None
        return self.stored

    async def delete(self, path: str) -> None:
        raise NotImplementedError("not used by GenerateImageAltTextUseCase")


def make_photo(**overrides: Any) -> ProductPhotoContext:
    defaults: dict[str, Any] = {
        "storage_path": "hero-abc123.webp",
        "product_name": "Funda Antigolpe",
        "product_model": "FA-100",
        "variant_color": "Negro",
    }
    defaults.update(overrides)
    return ProductPhotoContext(**defaults)


def make_use_case(
    *,
    generator: FakeContentGenerator,
    reader: FakeProductContextReader,
    storage: FakeObjectStorage,
) -> GenerateImageAltTextUseCase:
    return GenerateImageAltTextUseCase(
        content_generator=generator, context_reader=reader, object_storage=storage
    )


class TestOneImageInputCallPerInvocation:
    async def test_targets_exactly_one_image_with_exactly_one_gemini_call(self) -> None:
        photo = make_photo()
        generator = FakeContentGenerator(result={"alt_text": "Funda negra FA-100."})
        reader = FakeProductContextReader(photo=photo)
        storage = FakeObjectStorage(
            stored=StoredObject(data=b"webp-bytes", content_type="image/webp")
        )
        use_case = make_use_case(generator=generator, reader=reader, storage=storage)

        draft = await use_case.execute(uuid4(), uuid4())

        assert draft == AltTextDraft(alt_text="Funda negra FA-100.")
        assert len(generator.calls) == 1
        assert storage.get_calls == [photo.storage_path]

    async def test_image_input_carries_the_fetched_bytes_and_content_type(self) -> None:
        photo = make_photo(storage_path="variant-blue-xyz.webp")
        generator = FakeContentGenerator(result={"alt_text": "Funda azul FA-100."})
        reader = FakeProductContextReader(photo=photo)
        storage = FakeObjectStorage(
            stored=StoredObject(data=b"raw-image-bytes", content_type="image/png")
        )
        use_case = make_use_case(generator=generator, reader=reader, storage=storage)

        await use_case.execute(uuid4(), uuid4())

        sent_image = generator.calls[0]["image"]
        assert isinstance(sent_image, ImagePart)
        assert sent_image.data == b"raw-image-bytes"
        assert sent_image.mime_type == "image/png"


class TestNoPartialOutputLeniency:
    async def test_blank_alt_text_raises_generation_error(self) -> None:
        # DD6: unlike copy generation's two-field policy, alt text uses a
        # single-key schema with NO partial-output leniency.
        generator = FakeContentGenerator(result={"alt_text": "   "})
        reader = FakeProductContextReader(photo=make_photo())
        storage = FakeObjectStorage(
            stored=StoredObject(data=b"data", content_type="image/webp")
        )
        use_case = make_use_case(generator=generator, reader=reader, storage=storage)

        with pytest.raises(GenerationError):
            await use_case.execute(uuid4(), uuid4())

    async def test_missing_alt_text_key_raises_generation_error(self) -> None:
        generator = FakeContentGenerator(result={})
        reader = FakeProductContextReader(photo=make_photo())
        storage = FakeObjectStorage(
            stored=StoredObject(data=b"data", content_type="image/webp")
        )
        use_case = make_use_case(generator=generator, reader=reader, storage=storage)

        with pytest.raises(GenerationError):
            await use_case.execute(uuid4(), uuid4())

    async def test_non_json_generator_failure_propagates_as_generation_error(self) -> None:
        generator = FakeContentGenerator(
            error=GenerationError("Gemini returned non-JSON output")
        )
        reader = FakeProductContextReader(photo=make_photo())
        storage = FakeObjectStorage(
            stored=StoredObject(data=b"data", content_type="image/webp")
        )
        use_case = make_use_case(generator=generator, reader=reader, storage=storage)

        with pytest.raises(GenerationError):
            await use_case.execute(uuid4(), uuid4())


class TestOverCapTrimming:
    async def test_over_cap_alt_text_is_trimmed_to_its_own_cap(self) -> None:
        long_alt = " ".join(["palabra"] * 20)  # 160 chars, over 125
        assert len(long_alt) > ALT_TEXT_CAP
        generator = FakeContentGenerator(result={"alt_text": long_alt})
        reader = FakeProductContextReader(photo=make_photo())
        storage = FakeObjectStorage(
            stored=StoredObject(data=b"data", content_type="image/webp")
        )
        use_case = make_use_case(generator=generator, reader=reader, storage=storage)

        draft = await use_case.execute(uuid4(), uuid4())

        assert len(draft.alt_text) <= ALT_TEXT_CAP


class TestIDORGuard:
    async def test_unknown_or_cross_parent_image_raises_before_any_storage_or_gemini_call(
        self,
    ) -> None:
        # `photo_context` returning `None` covers both "unknown image id"
        # and "belongs to a different product" (design.md DD2's
        # ownership-via-query-scope) -- this use case must not distinguish
        # the two, mirroring `ProductImageRepository`'s existing 404-not-403
        # convention.
        generator = FakeContentGenerator(result={"alt_text": "unused"})
        reader = FakeProductContextReader(photo=None)
        storage = FakeObjectStorage(
            stored=StoredObject(data=b"data", content_type="image/webp")
        )
        use_case = make_use_case(generator=generator, reader=reader, storage=storage)
        image_id = uuid4()

        with pytest.raises(ImageNotFoundError):
            await use_case.execute(uuid4(), image_id)

        assert storage.get_calls == []
        assert generator.calls == []


class TestNoWriteSideEffect:
    async def test_storage_get_failure_propagates_without_a_gemini_call(self) -> None:
        # `ObjectStorage.get` raising `ObjectStorageError` (e.g. the object
        # was deleted out-of-band) must propagate, not be swallowed --
        # there is nothing to send to Gemini without the bytes.
        generator = FakeContentGenerator(result={"alt_text": "unused"})
        reader = FakeProductContextReader(photo=make_photo())
        storage = FakeObjectStorage(error=ObjectStorageError("object not found"))
        use_case = make_use_case(generator=generator, reader=reader, storage=storage)

        with pytest.raises(ObjectStorageError):
            await use_case.execute(uuid4(), uuid4())

        assert generator.calls == []
