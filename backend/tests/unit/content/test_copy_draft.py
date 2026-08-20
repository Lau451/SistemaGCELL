"""Unit tests for `content/domain/copy_draft.py` (design.md DD4).

Covers the three caps (blurb 160, body 1200, alt text 125) and
`trim_to_cap`'s word-boundary trimming rule: an over-cap draft is trimmed
at the last word boundary *within* the cap, never a hard mid-word cut
(design.md DD4: "Discarding an otherwise-good body over 20 excess
characters wastes a paid call. Residual: a trimmed blurb can end
mid-sentence -- visible and editable, which is the review gate working").
"""

from gcell.content.domain.copy_draft import (
    ALT_TEXT_CAP,
    DESCRIPTION_CAP,
    SHORT_DESCRIPTION_CAP,
    AltTextDraft,
    ProductCopyDraft,
    trim_to_cap,
)


class TestCaps:
    def test_short_description_cap_is_160(self) -> None:
        assert SHORT_DESCRIPTION_CAP == 160

    def test_description_cap_is_1200(self) -> None:
        assert DESCRIPTION_CAP == 1200

    def test_alt_text_cap_is_125(self) -> None:
        assert ALT_TEXT_CAP == 125


class TestTrimToCap:
    def test_text_within_cap_is_returned_unchanged(self) -> None:
        text = "Funda resistente y elegante."

        result = trim_to_cap(text, SHORT_DESCRIPTION_CAP)

        assert result == text

    def test_text_exactly_at_cap_is_returned_unchanged(self) -> None:
        text = "a" * SHORT_DESCRIPTION_CAP

        result = trim_to_cap(text, SHORT_DESCRIPTION_CAP)

        assert result == text
        assert len(result) == SHORT_DESCRIPTION_CAP

    def test_over_cap_blurb_trims_at_the_last_word_boundary_within_160(self) -> None:
        words = ["palabra"] * 25  # 25 * 8 ("palabra ") = 200 chars, over cap
        text = " ".join(words)
        assert len(text) > SHORT_DESCRIPTION_CAP

        result = trim_to_cap(text, SHORT_DESCRIPTION_CAP)

        assert len(result) <= SHORT_DESCRIPTION_CAP
        # Never a hard mid-word cut: either the whole string fit already,
        # or the character immediately following the trimmed text in the
        # original string is a space -- a real word boundary.
        assert result == text or text[len(result)] == " "
        assert all(word == "palabra" for word in result.split(" "))

    def test_over_cap_body_trims_at_the_last_word_boundary_within_1200(self) -> None:
        words = ["lorem"] * 250  # 250 * 6 = 1500 chars, over the 1200 cap
        text = " ".join(words)
        assert len(text) > DESCRIPTION_CAP

        result = trim_to_cap(text, DESCRIPTION_CAP)

        assert len(result) <= DESCRIPTION_CAP
        assert result == text or text[len(result)] == " "
        # No trailing partial word: the result splits cleanly into whole
        # "lorem" tokens.
        assert all(word == "lorem" for word in result.split(" "))

    def test_over_cap_alt_text_trims_at_the_last_word_boundary_within_125(self) -> None:
        words = ["celular"] * 20  # 20 * 8 = 160 chars, over the 125 cap
        text = " ".join(words)
        assert len(text) > ALT_TEXT_CAP

        result = trim_to_cap(text, ALT_TEXT_CAP)

        assert len(result) <= ALT_TEXT_CAP
        assert result == text or text[len(result)] == " "

    def test_no_space_within_cap_falls_back_to_a_hard_cut(self) -> None:
        # A single token longer than the cap has no word boundary to trim
        # at -- documented residual (design.md DD4), a hard cut is the
        # only option.
        text = "a" * (SHORT_DESCRIPTION_CAP + 10)

        result = trim_to_cap(text, SHORT_DESCRIPTION_CAP)

        assert len(result) == SHORT_DESCRIPTION_CAP


class TestProductCopyDraft:
    def test_holds_both_fields(self) -> None:
        draft = ProductCopyDraft(
            short_description="Funda resistente.", description="Una funda larga."
        )

        assert draft.short_description == "Funda resistente."
        assert draft.description == "Una funda larga."

    def test_either_field_may_be_none(self) -> None:
        draft = ProductCopyDraft(short_description=None, description="solo body")

        assert draft.short_description is None
        assert draft.description == "solo body"


class TestAltTextDraft:
    def test_holds_alt_text(self) -> None:
        draft = AltTextDraft(alt_text="Funda roja para telefono")

        assert draft.alt_text == "Funda roja para telefono"
