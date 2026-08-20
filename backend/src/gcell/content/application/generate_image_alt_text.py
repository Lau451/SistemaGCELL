"""Use case: generate a draft alt-text string for one product photo (DD1).

admin-ai-content-authoring spec, "Generate Alt Text Is A Separate,
Image-Input Action": generating alt text MUST be a distinct action from
generate-copy, MUST send the photo as image input to Gemini, and MUST
target exactly one existing image at a time (scenario "Alt text generation
targets one image").

`photo_context` (PR 8's DD2 seam) resolves ownership via
`ProductImageRepository.list_for_product`, so an unknown or cross-parent
`image_id` returns `None` here -- mapped to `ImageNotFoundError`
(404-never-403, same convention `UpdateProductImageAltTextUseCase` and
`DeleteProductImageUseCase` already use, Threat-Matrix "IDOR" row) before
any storage read or Gemini call is attempted.

`ObjectStorage.get` (this PR's DD1 addition) fetches the actual bytes --
Gemini's REST API needs `inline_data` (base64 bytes), not a URL, and
`supabase_url()` is a loopback address outside production (design.md
DD1). The fetched `StoredObject.content_type` becomes `ImagePart.mime_type`
verbatim -- the adapter's own response header is the authoritative mime
type, not a guess.

DD6's single-key schema gives alt-text generation NO partial-output
leniency (unlike `GenerateProductCopyUseCase`'s two-field policy): a
blank or missing `alt_text` means nothing was produced, so it is raised
as `GenerationError` immediately -- there is no second field to fall
back to.

Zero write side effect (D5, admin-ai-content-authoring spec "Generating
alt text does not persist anything"): the only three dependencies below
are `ContentGenerator`, `ProductContextReader`, and `ObjectStorage` (a
*read* via `get`, never `put`/`delete`) -- no repository import anywhere
in this module.
"""

from dataclasses import dataclass
from uuid import UUID

from gcell.ai.application.content_generator import ContentGenerator, GenerationError
from gcell.ai.domain.generation import ImagePart
from gcell.content.application.product_context_reader import ProductContextReader
from gcell.content.domain.copy_draft import ALT_TEXT_CAP, AltTextDraft, trim_to_cap
from gcell.products.application.exceptions import ImageNotFoundError
from gcell.shared.application.object_storage import ObjectStorage

_LANGUAGE = "es-AR"

_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {"alt_text": {"type": "STRING"}},
    "required": ["alt_text"],
}


def _build_instruction(
    product_name: str, product_model: str, variant_color: str | None
) -> str:
    color_text = variant_color or "sin color especifico"
    return (
        f"Escribi en {_LANGUAGE} un texto alternativo (alt text) breve y "
        f"descriptivo para esta foto de producto de e-commerce de "
        f"accesorios para celulares.\n"
        f"Nombre del producto: {product_name}\n"
        f"Modelo: {product_model}\n"
        f"Color: {color_text}\n"
        f"Devolve un 'alt_text' de menos de {ALT_TEXT_CAP} caracteres que "
        f"describa la imagen para un lector de pantalla. No menciones ni "
        f"inventes precio ni costo."
    )


def _blank_to_none(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


@dataclass
class GenerateImageAltTextUseCase:
    """Composed at the API layer (`api/admin.py`, PR 11) with the real
    `GeminiContentGenerator` (PR 7), `ProductsContextReader` (PR 8), and
    `SupabaseStorage` (this PR's `get` addition). Wired to no route yet --
    this PR ships the use case, exercised only by its own unit tests.
    """

    content_generator: ContentGenerator
    context_reader: ProductContextReader
    object_storage: ObjectStorage

    async def execute(self, product_id: UUID, image_id: UUID) -> AltTextDraft:
        photo = await self.context_reader.photo_context(product_id, image_id)
        if photo is None:
            raise ImageNotFoundError(image_id, product_id)

        stored = await self.object_storage.get(photo.storage_path)
        image = ImagePart(data=stored.data, mime_type=stored.content_type)

        instruction = _build_instruction(
            photo.product_name, photo.product_model, photo.variant_color
        )
        result = await self.content_generator.generate_json(
            instruction=instruction,
            response_schema=_RESPONSE_SCHEMA,
            image=image,
        )

        alt_text = _blank_to_none(result.get("alt_text"))
        if alt_text is None:
            raise GenerationError(
                "Gemini returned no usable alt text: alt_text was blank or missing"
            )

        return AltTextDraft(alt_text=trim_to_cap(alt_text, ALT_TEXT_CAP))
