import json
from typing import Any

import httpx
import pytest
from PIL import Image

from app.errors import ApiError
from app.vision import OllamaVision

GOOD = {
    "slug": "northgate-market-receipt",
    "category": "receipt",
    "description": "A grocery till receipt.",
    "text": "NORTHGATE MARKET",
    "sensitive": False,
    "expiry_hint": None,
}


def image() -> Image.Image:
    return Image.new("RGB", (64, 48), "white")


def transport(*bodies: object, status: int = 200) -> httpx.MockTransport:
    """Answers each call with the next body, so a retry can be given different content."""
    remaining = list(bodies)

    def handler(_request: httpx.Request) -> httpx.Response:
        content = remaining.pop(0) if remaining else bodies[-1]
        if isinstance(content, int):
            return httpx.Response(content)
        payload = content if isinstance(content, str) else json.dumps(content)
        return httpx.Response(
            status, json={"message": {"content": payload}, "total_duration": 1_500_000_000}
        )

    return httpx.MockTransport(handler)


def vision(tr: httpx.MockTransport, model: str | None = "m:1") -> OllamaVision:
    return OllamaVision("http://127.0.0.1:11434", lambda: model, transport=tr)


def test_parses_a_clean_answer_and_reports_ollamas_own_timing() -> None:
    result = vision(transport(GOOD)).analyze(image())
    assert result.analysis.slug == "northgate-market-receipt"
    assert result.analysis.category.value == "receipt"
    assert result.seconds == pytest.approx(1.5)
    assert result.retried is False


def test_recovers_an_object_wrapped_in_prose() -> None:
    """Some models add a sentence around the JSON despite being given a schema."""
    wrapped = f"Sure, here is the result:\n```json\n{json.dumps(GOOD)}\n```"
    result = vision(transport(wrapped)).analyze(image())
    assert result.analysis.category.value == "receipt"
    assert result.retried is False


def test_retries_once_and_succeeds() -> None:
    result = vision(transport("not json at all", GOOD)).analyze(image())
    assert result.analysis.slug == "northgate-market-receipt"
    assert result.retried is True


def test_gives_up_after_one_retry() -> None:
    with pytest.raises(ApiError) as caught:
        vision(transport("nope", "still nope")).analyze(image())
    assert caught.value.code == "invalid_model_output"


def test_a_schema_shaped_answer_with_a_bad_category_is_still_refused() -> None:
    bad = GOOD | {"category": "screenshot"}
    with pytest.raises(ApiError) as caught:
        vision(transport(bad, bad)).analyze(image())
    assert caught.value.code == "invalid_model_output"


def test_refuses_when_no_model_is_chosen() -> None:
    with pytest.raises(ApiError) as caught:
        vision(transport(GOOD), model=None).analyze(image())
    assert caught.value.code == "vision_model_not_set"


def test_missing_model_is_reported_as_such() -> None:
    with pytest.raises(ApiError) as caught:
        vision(transport(404)).analyze(image())
    assert caught.value.code == "vision_model_missing"


def test_unreachable_engine_is_reported_as_such() -> None:
    def refuse(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no listener")

    with pytest.raises(ApiError) as caught:
        vision(httpx.MockTransport(refuse)).analyze(image())
    assert caught.value.code == "vision_unreachable"


def test_the_request_constrains_the_model_rather_than_asking_politely() -> None:
    seen: dict[str, Any] = {}

    def capture(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200, json={"message": {"content": json.dumps(GOOD)}, "total_duration": 1}
        )

    vision(httpx.MockTransport(capture)).analyze(image())

    assert seen["think"] is False  # the recommended models default to thinking on
    assert seen["options"] == {"temperature": 0}
    assert seen["stream"] is False
    assert seen["format"]["properties"]["category"]  # the schema is handed over, not described
    assert seen["messages"][0]["images"]  # the image rides on the message
