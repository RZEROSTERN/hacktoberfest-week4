import threading

import httpx
import pytest

from app.compat import CHECK_TOKEN, CHECK_WORD, CompatError, OllamaCompatChecker, test_image


def answering(**fields: object) -> httpx.MockTransport:
    body = {
        "slug": "a-card",
        "category": "other",
        "description": "A card.",
        "text": "",
        "sensitive": False,
    } | fields

    def handler(_request: httpx.Request) -> httpx.Response:
        import json

        return httpx.Response(
            200, json={"message": {"content": json.dumps(body)}, "total_duration": 1}
        )

    return httpx.MockTransport(handler)


def checker(transport: httpx.MockTransport) -> OllamaCompatChecker:
    return OllamaCompatChecker("http://127.0.0.1:11434", transport=transport)


class TestTheTestImage:
    def test_carries_the_token_a_blind_model_cannot_guess(self) -> None:
        image = test_image()
        assert image.size == (640, 360)
        assert image.mode == "RGB"
        # Rendered, not shipped, so there is no asset to go missing from the packaged binary.
        assert CHECK_TOKEN.isdigit() and len(CHECK_TOKEN) == 4


class TestCheck:
    def test_passes_when_the_model_read_the_token(self) -> None:
        checker(answering(text=f"{CHECK_WORD} {CHECK_TOKEN}")).check("m:1", threading.Event())

    def test_passes_on_the_word_alone(self) -> None:
        checker(answering(description=f"A card reading {CHECK_WORD}.")).check(
            "m:1", threading.Event()
        )

    def test_a_text_only_model_fails_even_with_a_perfectly_shaped_answer(self) -> None:
        """The exact failure the check exists for: valid JSON, invented content."""
        with pytest.raises(CompatError) as caught:
            checker(
                answering(
                    slug="a-screenshot",
                    description="A screenshot of an application window.",
                    text="Some text appears in the image.",
                )
            ).check("m:1", threading.Event())
        assert caught.value.code == "compat_no_vision"

    def test_an_unparseable_answer_is_reported_as_such(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"message": {"content": "not json"}, "total_duration": 1}
            )

        with pytest.raises(CompatError) as caught:
            checker(httpx.MockTransport(handler)).check("m:1", threading.Event())
        assert caught.value.code == "compat_invalid_output"

    def test_a_missing_model_is_not_blamed_on_the_model_being_blind(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(404)

        with pytest.raises(CompatError) as caught:
            checker(httpx.MockTransport(handler)).check("m:1", threading.Event())
        assert caught.value.code == "compat_model_missing"

    def test_an_unreachable_engine_is_reported_as_such(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no listener")

        with pytest.raises(CompatError) as caught:
            checker(httpx.MockTransport(handler)).check("m:1", threading.Event())
        assert caught.value.code == "ollama_unreachable"
