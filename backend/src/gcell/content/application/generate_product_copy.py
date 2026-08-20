"""Use case: generate a draft product-copy pair in one Gemini call (D10).

admin-ai-content-authoring spec, "Generate Copy Returns Both Fields From
One Gemini Call": a single "generate copy" action MUST invoke Gemini
exactly once and return both `short_description` and `description` as a
draft pair -- never two separate calls or two separate actions.

The prompt is built from `ProductCopyContext.{name,model,colors}` only --
price/cost never reach this module because `ProductCopyContext`
structurally has no such field (DD2/OQ2; see
`content/application/product_context_reader.py`). This is the same
spec requirement as "Generation Excludes Price From The Prompt" /
"Price is absent from the generation input".

DD6's structured-JSON `response_schema` requires both keys, but the
partial-output policy is applied AFTER parsing, not by the schema:

- both fields non-blank after strip -> `200`-shaped draft, each field
  independently trimmed to its own cap (DD4);
- exactly one field blank or missing -> still a `200`-shaped draft, with
  that field `None` (the UI marks it "not generated" -- a half-useful
  draft beats a hard failure that already burned the paid call, D6);
- both blank or missing -> `GenerationError` (`502 generation_failed` at
  the route layer, PR 11) -- nothing left to review.

A non-JSON or malformed Gemini response is detected and raised as
`GenerationError` by the adapter itself (`ai/infrastructure/
gemini_content_generator.py`, PR 7) before it ever reaches this module --
this use case only has to decide the blank-vs-populated policy on an
already-parsed mapping.

Zero write side effect (D5, admin-ai-content-authoring spec "Content
Never Persists Products Or Images Directly" / "Generating copy does not
persist anything"): the only two dependencies below are `ContentGenerator`
and `ProductContextReader` -- there is no repository import anywhere in
this module, so "no write handler touches a repository" is
unfalsifiable-by-construction, not a review duty.

Prompt-injection defense (Threat-Matrix "Prompt injection via product
data" row): `name`/`model`/`colors` are admin-typed free text
interpolated verbatim into the instruction string. The actual security
boundary is Gemini's `responseSchema` (enforced by the PR 7 adapter),
which constrains the model's output to exactly the two declared string
fields -- no amount of instruction-like text inside a product name can
make the response escape that shape. This use case's own job is simply
to never treat the parsed result as anything other than draft text: it
is never executed, never used to build another prompt, and never used to
choose a control-flow branch.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from gcell.ai.application.content_generator import ContentGenerator, GenerationError
from gcell.content.application.product_context_reader import ProductContextReader
from gcell.content.domain.copy_draft import (
    DESCRIPTION_CAP,
    SHORT_DESCRIPTION_CAP,
    ProductCopyDraft,
    trim_to_cap,
)
from gcell.products.application.exceptions import ProductNotFoundError

# Verified against `supabase/seed.sql` (design.md DD4): every product
# `name`, `model`, `color`, and the one existing `description` are
# Spanish, prices in ARS. Hardcoded on purpose -- never configurable
# (design.md's own framing of the language choice).
_LANGUAGE = "es-AR"

_RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "short_description": {"type": "STRING"},
        "description": {"type": "STRING"},
    },
    "required": ["short_description", "description"],
}


def _build_instruction(name: str, model: str, colors: list[str]) -> str:
    colors_text = ", ".join(colors) if colors else "sin colores registrados"
    return (
        f"Escribi en {_LANGUAGE} textos de marketing para un producto de "
        f"e-commerce de accesorios para celulares.\n"
        f"Nombre del producto: {name}\n"
        f"Modelo: {model}\n"
        f"Colores disponibles: {colors_text}\n"
        f"Devolve un 'short_description' (una bajada corta para una "
        f"tarjeta de catalogo, menos de {SHORT_DESCRIPTION_CAP} caracteres) "
        f"y una 'description' (un parrafo mas largo para la ficha del "
        f"producto, menos de {DESCRIPTION_CAP} caracteres). No menciones "
        f"ni inventes precio ni costo."
    )


def _blank_to_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


@dataclass
class GenerateProductCopyUseCase:
    """Composed at the API layer (`api/admin.py`, PR 11) with the real
    `GeminiContentGenerator` (PR 7) and `ProductsContextReader` (PR 8).
    Wired to no route yet -- this PR ships the use case, exercised only
    by its own unit tests.
    """

    content_generator: ContentGenerator
    context_reader: ProductContextReader

    async def execute(self, product_id: UUID) -> ProductCopyDraft:
        context = await self.context_reader.product_context(product_id)
        if context is None:
            raise ProductNotFoundError(product_id)

        instruction = _build_instruction(context.name, context.model, context.colors)
        result = await self.content_generator.generate_json(
            instruction=instruction,
            response_schema=_RESPONSE_SCHEMA,
        )

        short_description = _blank_to_none(result.get("short_description"))
        description = _blank_to_none(result.get("description"))

        if short_description is None and description is None:
            raise GenerationError(
                "Gemini returned no usable product copy: both "
                "short_description and description were blank or missing"
            )

        if short_description is not None:
            short_description = trim_to_cap(short_description, SHORT_DESCRIPTION_CAP)
        if description is not None:
            description = trim_to_cap(description, DESCRIPTION_CAP)

        return ProductCopyDraft(
            short_description=short_description, description=description
        )
