"""Asking the local vision model to describe one screenshot.

Nothing here logs image bytes, extracted text, file names or paths: errors carry a stable code
and nothing else. See .claude/rules/api.md.
"""

import base64
import io
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx
from PIL import Image
from pydantic import ValidationError

from app.errors import ApiError
from app.schemas import Analysis

# Short, so the model carries between screenshots in a run without holding memory afterwards.
KEEP_ALIVE = "30s"
PROMPT_VERSION = "analyze.v1"


def default_prompts_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(prompts_dir: Path | None = None, version: str = PROMPT_VERSION) -> str:
    return (prompts_dir or default_prompts_dir()).joinpath(f"{version}.txt").read_text("utf-8")


def encode(image: Image.Image) -> str:
    """PNG, base64. PNG rather than JPEG so text stays crisp at small sizes."""
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


@dataclass(frozen=True)
class VisionResult:
    analysis: Analysis
    seconds: float
    retried: bool
    model: str
    prompt_version: str


class Vision(Protocol):
    """What a run needs from the model; tests replace it with a scripted stand-in."""

    def analyze(self, image: Image.Image) -> VisionResult: ...

    def unload(self) -> None: ...


class OllamaVision:
    """Chat completion against a local Ollama, constrained to the Analysis schema.

    `format` is handed the JSON schema so the model is constrained rather than asked politely.
    `think` is false because the recommended models default to thinking on, which costs seconds
    per image and buries the JSON in prose.
    """

    def __init__(
        self,
        base_url: str,
        model: Callable[[], str | None],
        prompts_dir: Path | None = None,
        timeout: float = 180.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._prompt = load_prompt(prompts_dir)
        self._schema = Analysis.model_json_schema()
        self._timeout = timeout
        self._transport = transport

    def _payload(self, encoded: str, model: str) -> dict[str, Any]:
        return {
            "model": model,
            "stream": False,
            "think": False,
            "format": self._schema,
            "keep_alive": KEEP_ALIVE,
            "options": {"temperature": 0},
            "messages": [{"role": "user", "content": self._prompt, "images": [encoded]}],
        }

    def _call(self, payload: dict[str, Any]) -> tuple[str, float]:
        try:
            with httpx.Client(
                base_url=self._base_url, timeout=self._timeout, transport=self._transport
            ) as client:
                response = client.post("/api/chat", json=payload)
        except httpx.ConnectError as exc:
            raise ApiError(503, "vision_unreachable") from exc
        except httpx.TimeoutException as exc:
            raise ApiError(504, "vision_timeout") from exc
        except httpx.HTTPError as exc:
            raise ApiError(502, "vision_failed") from exc

        if response.status_code == 404:
            raise ApiError(400, "vision_model_missing")
        if response.status_code >= 400:
            raise ApiError(502, "vision_failed")

        body = response.json()
        # Ollama reports its own timing in nanoseconds; it excludes transport, which is what we
        # want when comparing models.
        elapsed = float(body.get("total_duration", 0)) / 1e9
        return body.get("message", {}).get("content", ""), elapsed

    def unload(self) -> None:
        """Ask Ollama to drop the model from memory now, rather than after the keep-alive.

        A run is a queue of single images; once it ends, holding several gigabytes for another
        half minute is the difference between a good neighbour and a bad one. Ollama documents
        a request carrying `keep_alive: 0` as the way to unload.

        Failures are ignored on purpose: the keep-alive will do it shortly anyway, and a run
        that finished successfully must not be reported as failed over this.
        """
        model = self._model()
        if not model:
            return
        try:
            with httpx.Client(
                base_url=self._base_url, timeout=30, transport=self._transport
            ) as client:
                client.post("/api/generate", json={"model": model, "keep_alive": 0})
        except httpx.HTTPError:
            pass

    def analyze(self, image: Image.Image) -> VisionResult:
        model = self._model()
        if not model:
            raise ApiError(400, "vision_model_not_set")

        encoded = encode(image)
        payload = self._payload(encoded, model)

        total = 0.0
        for attempt in (0, 1):  # one retry, then the caller marks the file skipped
            content, elapsed = self._call(payload)
            total += elapsed
            try:
                analysis = Analysis.model_validate_json(content)
            except (ValidationError, ValueError):
                # Some models wrap the object in prose despite `format`; try the first {...} span.
                try:
                    analysis = Analysis.model_validate(_first_object(content))
                except (ValidationError, ValueError, json.JSONDecodeError):
                    if attempt == 1:
                        raise ApiError(422, "invalid_model_output") from None
                    continue
            return VisionResult(
                analysis=analysis,
                seconds=total,
                retried=attempt == 1,
                model=model,
                prompt_version=PROMPT_VERSION,
            )
        raise ApiError(422, "invalid_model_output")


def _first_object(content: str) -> dict[str, Any]:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in the answer")
    parsed: dict[str, Any] = json.loads(content[start : end + 1])
    return parsed
