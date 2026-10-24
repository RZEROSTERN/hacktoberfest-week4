import pytest
from pydantic import ValidationError

from app.models import Category
from app.schemas import Analysis


def analysis(**overrides: object) -> Analysis:
    data = {"slug": "a-b", "category": "receipt"} | overrides
    return Analysis.model_validate(data)


class TestSlug:
    def test_keeps_a_clean_slug(self) -> None:
        assert analysis(slug="northgate-market-grocery-receipt").slug == (
            "northgate-market-grocery-receipt"
        )

    def test_strips_an_extension_the_model_added(self) -> None:
        assert analysis(slug="boarding-pass.png").slug == "boarding-pass"

    def test_lowercases_and_rejoins_spaces_and_underscores(self) -> None:
        assert analysis(slug="Boarding Pass_MXP").slug == "boarding-pass-mxp"

    def test_drops_accents_and_punctuation_so_filenames_stay_portable(self) -> None:
        # The slug becomes part of a filename on three operating systems.
        assert analysis(slug="café — receipt (2026)!").slug == "caf-receipt-2026"

    def test_caps_the_number_of_words(self) -> None:
        got = analysis(slug="one-two-three-four-five-six-seven-eight").slug
        assert got == "one-two-three-four-five-six"

    def test_refuses_a_slug_that_cleans_away_to_nothing(self) -> None:
        with pytest.raises(ValidationError):
            analysis(slug="!!! ???")


class TestOtherFields:
    def test_category_must_be_one_of_the_ten(self) -> None:
        assert analysis(category="error message").category is Category.ERROR_MESSAGE
        with pytest.raises(ValidationError):
            analysis(category="screenshot")

    def test_text_is_capped_so_one_model_cannot_bloat_the_index(self) -> None:
        assert len(analysis(text="x" * 5000).text) == 2000

    def test_blank_expiry_becomes_none(self) -> None:
        assert analysis(expiry_hint="   ").expiry_hint is None
        assert analysis(expiry_hint=None).expiry_hint is None
        assert analysis(expiry_hint=" flight 4 Feb ").expiry_hint == "flight 4 Feb"

    def test_defaults_are_safe_when_the_model_omits_fields(self) -> None:
        minimal = analysis()
        assert minimal.sensitive is False
        assert minimal.text == ""
        assert minimal.expiry_hint is None
