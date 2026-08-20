"""Thin httpx adapter over the Gemini REST `:generateContent` API.

Mirrors `shared/infrastructure/supabase_storage.py`'s adapter shape byte for
byte (design.md DD4/D8): constructor-injected `transport` so every test runs
under `httpx.MockTransport` with zero live network call. `httpx` stays
confined to `ai/infrastructure/` -- never imported from `ai/domain/` (see
`test_domain_boundary.py`'s `BANNED_MODULES`).

Structured-JSON output (DD6): `generationConfig.responseSchema` constrains
the model's output shape, so `content/` never needs delimiter parsing --
naming ("product copy", "alt text") stays `content`'s job, not `ai`'s.

No retry (DD4 / D6 cost guardrail): a 4xx/5xx/timeout maps straight to
`GenerationError`. An automatic retry would silently double a paid call per
click and would require a sleep/backoff loop that breaks mock-transport
test determinism -- see the Threat-Matrix "Process integration" row
(exactly one request per invocation) and this file's own test suite.

`GEMINI_API_KEY` is sent ONLY in the `x-goog-api-key` request header
(Threat-Matrix "Secret exposure" row) -- never interpolated into a raised
exception's message; every `raise` below only ever includes the Gemini
response's own status code / body / block reason.
"""

import base64
import json
from collections.abc import Mapping
from typing import Any

import httpx

from gcell.ai.application.content_generator import (
    ContentGenerator,
    GenerationError,
    GenerationRefusedError,
)
from gcell.ai.domain.generation import ImagePart

_BASE_URL = "https://generativelanguage.googleapis.com"
_API_VERSION = "v1beta"
_TEMPERATURE = 0.4


class GeminiContentGenerator(ContentGenerator):
    """The only production `ContentGenerator` (design.md DD6).

    Not wired into any use case yet -- that lands in PR 9/10, which call
    `generate_json` through the `content/` domain's two use cases. This PR
    ships the adapter and its mock-transport test suite only.
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._client = httpx.AsyncClient(
            base_url=_BASE_URL,
            headers={"x-goog-api-key": api_key},
            timeout=httpx.Timeout(30.0, connect=5.0),
            transport=transport,
        )

    async def generate_json(
        self,
        *,
        instruction: str,
        response_schema: Mapping[str, Any],
        image: ImagePart | None = None,
        max_output_tokens: int = 1024,
    ) -> Mapping[str, Any]:
        parts: list[dict[str, Any]] = [{"text": instruction}]
        if image is not None:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": image.mime_type,
                        "data": base64.b64encode(image.data).decode("ascii"),
                    }
                }
            )

        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseSchema": dict(response_schema),
                "temperature": _TEMPERATURE,
                "maxOutputTokens": max_output_tokens,
            },
        }

        try:
            response = await self._client.post(
                f"/{_API_VERSION}/models/{self._model}:generateContent",
                json=body,
            )
        except httpx.TimeoutException as exc:
            raise GenerationError("Gemini call timed out") from exc

        if response.status_code >= 400:
            raise GenerationError(
                f"Gemini call failed: {response.status_code} {response.text}"
            )

        payload = response.json()

        prompt_feedback = payload.get("promptFeedback") or {}
        block_reason = prompt_feedback.get("blockReason")
        if block_reason:
            raise GenerationRefusedError(
                f"Gemini refused the request: blockReason={block_reason}"
            )

        candidates = payload.get("candidates") or []
        if not candidates:
            raise GenerationRefusedError("Gemini returned no usable candidate")

        try:
            text = candidates[0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise GenerationError(
                "Gemini response is missing the expected generated text"
            ) from exc

        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError) as exc:
            raise GenerationError("Gemini returned non-JSON output") from exc

        if not isinstance(parsed, Mapping):
            raise GenerationError("Gemini returned a non-object JSON payload")

        return parsed
