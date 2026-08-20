"""Domain-agnostic Gemini generation port (D9: `ai` stays domain-agnostic).

`content/` is the only caller (DD5's `ALLOWED_EDGES`: `content -> {ai,
products}`, `ai: set()`); this port itself names nothing product- or
copy-specific -- naming ("product copy", "alt text") is `content`'s job,
not `ai`'s (design.md DD6). The only implementation is the `httpx` Gemini
adapter in `ai/infrastructure/gemini_content_generator.py` (PR 7); this PR
ships the port and its error types only, with zero live call.
"""

from collections.abc import Mapping
from typing import Any, Protocol

from gcell.ai.domain.generation import ImagePart


class ContentGenerator(Protocol):
    """Port implemented by `ai/infrastructure/gemini_content_generator.py`."""

    async def generate_json(
        self,
        *,
        instruction: str,
        response_schema: Mapping[str, Any],
        image: ImagePart | None = None,
        max_output_tokens: int = 1024,
    ) -> Mapping[str, Any]:
        """Return the parsed JSON object the model produced.

        Raises `GenerationError` on a transport/status/timeout/malformed
        failure, or `GenerationRefusedError` on a safety block / no usable
        candidate (design.md DD4's failure-mapping table). Never returns
        an empty-but-successful mapping in place of raising.
        """
        ...


class GenerationError(Exception):
    """Raised on a transport/status/timeout/malformed-response failure.

    Maps to `502 generation_failed` at the route layer (design.md DD4) --
    the same 503-when-unconfigured / 502-when-the-call-fails split as
    `ObjectStorageError`.
    """


class GenerationRefusedError(GenerationError):
    """Raised on a safety block (`promptFeedback.blockReason`) or a
    `finishReason` outside `{STOP, MAX_TOKENS}` with no usable candidate.

    Maps to `502 generation_refused` at the route layer (design.md DD4) --
    a distinct `detail` from `GenerationError`'s `generation_failed` so the
    UI can say "the model declined" rather than "the call failed".
    """
