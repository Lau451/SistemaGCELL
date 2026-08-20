"""Unit tests for the httpx-backed `GeminiContentGenerator` adapter.

No live network/Gemini call -- `httpx.MockTransport` fakes the transport
layer entirely, mirroring `test_supabase_storage.py`'s exact pattern
(design.md DD4/D8, Testing Strategy: "Unit (ai adapter) ... httpx.MockTransport,
mirroring test_supabase_storage.py. Zero network"). This is the only test
file for this PR (7.1) -- no runtime harness exists or should exist
pre-key (tasks.md Phase 7's Runtime harness column).
"""

import json

import httpx
import pytest

from gcell.ai.application.content_generator import (
    GenerationError,
    GenerationRefusedError,
)
from gcell.ai.domain.generation import ImagePart
from gcell.ai.infrastructure.gemini_content_generator import GeminiContentGenerator

_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "short_description": {"type": "STRING"},
        "description": {"type": "STRING"},
    },
    "required": ["short_description", "description"],
}


def _generator(handler, *, api_key: str = "test-gemini-key") -> GeminiContentGenerator:
    return GeminiContentGenerator(
        api_key=api_key,
        model="gemini-2.5-flash",
        transport=httpx.MockTransport(handler),
    )


def _success_response(payload: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(payload)}]}},
            ]
        },
    )


class TestRequestShape:
    async def test_sends_instruction_and_schema_with_no_inline_data_when_image_is_none(
        self,
    ) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["url"] = str(request.url)
            captured["headers"] = request.headers
            captured["body"] = json.loads(request.content)
            return _success_response({"short_description": "a", "description": "b"})

        generator = _generator(handler)

        result = await generator.generate_json(
            instruction="write copy", response_schema=_SCHEMA
        )

        assert result == {"short_description": "a", "description": "b"}
        assert captured["method"] == "POST"
        assert "/v1beta/models/gemini-2.5-flash:generateContent" in captured["url"]
        assert captured["headers"]["x-goog-api-key"] == "test-gemini-key"
        parts = captured["body"]["contents"][0]["parts"]
        assert parts == [{"text": "write copy"}]
        assert not any("inline_data" in part for part in parts)
        gen_config = captured["body"]["generationConfig"]
        assert gen_config["responseMimeType"] == "application/json"
        assert gen_config["responseSchema"] == _SCHEMA

    async def test_sends_inline_data_when_an_image_part_is_given(self) -> None:
        captured: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _success_response({"alt_text": "a red phone case"})

        generator = _generator(handler)
        image = ImagePart(data=b"raw-bytes", mime_type="image/webp")

        await generator.generate_json(
            instruction="describe this image",
            response_schema={"type": "OBJECT"},
            image=image,
        )

        parts = captured["body"]["contents"][0]["parts"]
        assert len(parts) == 2
        assert parts[0] == {"text": "describe this image"}
        inline_data = parts[1]["inline_data"]
        assert inline_data["mime_type"] == "image/webp"
        # base64 of b"raw-bytes"
        import base64

        assert base64.b64decode(inline_data["data"]) == b"raw-bytes"


class TestSuccessPath:
    async def test_parses_candidates_text_as_json(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return _success_response(
                {"short_description": "Funda resistente", "description": "Larga"}
            )

        generator = _generator(handler)

        result = await generator.generate_json(
            instruction="write copy", response_schema=_SCHEMA
        )

        assert result == {
            "short_description": "Funda resistente",
            "description": "Larga",
        }


class TestFailureMapping:
    async def test_4xx_status_raises_generation_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": {"message": "bad request"}})

        generator = _generator(handler)

        with pytest.raises(GenerationError):
            await generator.generate_json(instruction="x", response_schema=_SCHEMA)

    async def test_5xx_status_raises_generation_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": {"message": "internal error"}})

        generator = _generator(handler)

        with pytest.raises(GenerationError):
            await generator.generate_json(instruction="x", response_schema=_SCHEMA)

    async def test_timeout_raises_generation_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out", request=request)

        generator = _generator(handler)

        with pytest.raises(GenerationError):
            await generator.generate_json(instruction="x", response_schema=_SCHEMA)

    async def test_block_reason_raises_generation_refused_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "candidates": [],
                    "promptFeedback": {"blockReason": "SAFETY"},
                },
            )

        generator = _generator(handler)

        with pytest.raises(GenerationRefusedError):
            await generator.generate_json(instruction="x", response_schema=_SCHEMA)

    async def test_no_candidates_raises_generation_refused_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"candidates": []})

        generator = _generator(handler)

        with pytest.raises(GenerationRefusedError):
            await generator.generate_json(instruction="x", response_schema=_SCHEMA)

    async def test_non_json_text_raises_generation_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={
                    "candidates": [
                        {"content": {"parts": [{"text": "not-json-at-all"}]}},
                    ]
                },
            )

        generator = _generator(handler)

        with pytest.raises(GenerationError):
            await generator.generate_json(instruction="x", response_schema=_SCHEMA)

    async def test_malformed_response_missing_parts_raises_generation_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                json={"candidates": [{"content": {}}]},
            )

        generator = _generator(handler)

        with pytest.raises(GenerationError):
            await generator.generate_json(instruction="x", response_schema=_SCHEMA)


class TestNoRetry:
    async def test_handler_is_called_exactly_once_on_failure(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(503, json={"error": {"message": "unavailable"}})

        generator = _generator(handler)

        with pytest.raises(GenerationError):
            await generator.generate_json(instruction="x", response_schema=_SCHEMA)

        assert call_count == 1

    async def test_handler_is_called_exactly_once_on_success(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return _success_response({"short_description": "a", "description": "b"})

        generator = _generator(handler)

        await generator.generate_json(instruction="x", response_schema=_SCHEMA)

        assert call_count == 1


class TestSecretExposure:
    async def test_api_key_appears_only_in_the_request_header(self) -> None:
        captured_headers: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured_headers.update(request.headers)
            return httpx.Response(500, json={"error": {"message": "internal error"}})

        generator = _generator(handler, api_key="super-secret-gemini-key")

        with pytest.raises(GenerationError) as exc_info:
            await generator.generate_json(instruction="x", response_schema=_SCHEMA)

        assert captured_headers["x-goog-api-key"] == "super-secret-gemini-key"
        assert "super-secret-gemini-key" not in str(exc_info.value)

    async def test_api_key_never_leaks_into_a_timeout_exception_message(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out", request=request)

        generator = _generator(handler, api_key="super-secret-gemini-key")

        with pytest.raises(GenerationError) as exc_info:
            await generator.generate_json(instruction="x", response_schema=_SCHEMA)

        assert "super-secret-gemini-key" not in str(exc_info.value)
