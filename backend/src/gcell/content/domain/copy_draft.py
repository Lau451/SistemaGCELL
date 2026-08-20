"""Pure domain types for generated product-copy/alt-text drafts (DD4/DD6).

`ProductCopyDraft`/`AltTextDraft` are the value objects
`content/application/generate_product_copy.py` (this PR) and
`generate_image_alt_text.py` (PR 10) return -- never persisted directly.
Generation has zero write side effect (D5): a draft is only ever saved
through the `products` domain's existing write path, via an explicit,
separate admin action.

Caps mirror design.md DD4's table exactly: blurb 160, body 1200, alt text
125 chars. `AltTextDraft` is defined here (its 125-char cap included) but
has no producing use case until PR 10 -- this PR only needs
`ProductCopyDraft` wired into `GenerateProductCopyUseCase`.
"""

from dataclasses import dataclass

SHORT_DESCRIPTION_CAP = 160
DESCRIPTION_CAP = 1200
ALT_TEXT_CAP = 125


def trim_to_cap(text: str, cap: int) -> str:
    """Trim `text` to at most `cap` characters at the last word boundary.

    Never a hard mid-word cut (design.md DD4: "Trim at the last word
    boundary within the cap, return the draft" -- D5 makes every draft
    human-reviewed and editable before save, so discarding an
    otherwise-good body over a few excess characters would waste a paid
    call). Text already within `cap` is returned unchanged. If `text` has
    no space within the first `cap` characters (a single very long
    token), the cap is used as a hard cut -- the documented residual: a
    trimmed blurb can end mid-sentence or mid-word in that edge case,
    visible and editable, which is the review gate working as intended.
    """
    if len(text) <= cap:
        return text

    truncated = text[:cap]
    last_space = truncated.rfind(" ")
    if last_space == -1:
        return truncated
    return truncated[:last_space]


@dataclass(frozen=True)
class ProductCopyDraft:
    """Draft pair returned by generate-copy (D10: one Gemini call, two
    fields, never two separate calls or actions).

    Either field may be `None` -- DD6's partial-output policy: the model
    returning exactly one field blank/missing is still a usable `200`
    draft, marked "not generated" by the UI for that field, not a
    failure. `GenerateProductCopyUseCase` raises `GenerationError` only
    when BOTH fields are blank/missing (nothing left to review).
    """

    short_description: str | None
    description: str | None


@dataclass(frozen=True)
class AltTextDraft:
    """Draft returned by generate-alt-text (PR 10's use case).

    Unlike `ProductCopyDraft`, DD6 gives alt-text generation no
    partial-output leniency: a blank/missing `alt_text` is raised as a
    `GenerationError` upstream in the use case, so `alt_text` here is
    never `None` once a draft is actually constructed.
    """

    alt_text: str
