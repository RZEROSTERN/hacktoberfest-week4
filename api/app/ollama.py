"""Ollama's model-management endpoints: list, pull (with streaming progress) and delete.

Only documented endpoints are used: GET /api/tags, POST /api/pull, DELETE /api/delete. The docs
do not describe a pull's error text; the messages matched below were observed on Ollama 0.35.1.
"""

import json
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.errors import Cancelled

# `error` lines Ollama sends when its own connection to the registry breaks.
_NETWORK_HINTS = re.compile(
    r"dial tcp|no such host|connection reset|connection refused|timeout|timed out|eof|"
    r"max retries|network|unexpected end|broken pipe|tls",
    re.IGNORECASE,
)


class OllamaError(Exception):
    """A failure with a stable `code` the UI turns into a plain-language message."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class InstalledModel:
    name: str
    size_bytes: int
    remote_host: str | None  # set for cloud models, which run on someone else's server


class ModelEngine(Protocol):
    """What the setup needs from the model engine (Ollama); tests replace it with a script."""

    def reachable(self) -> bool: ...

    def list_models(self) -> list[InstalledModel]: ...

    def installed(self, name: str) -> InstalledModel | None: ...

    def delete(self, name: str) -> None: ...

    def pull(
        self, name: str, on_progress: Callable[[int, int], None], cancel: threading.Event
    ) -> None: ...


class LayerProgress:
    """Sums bytes over the layers of a pull and never reports less than it already has.

    Ollama reports progress layer by layer: the big weights layer first, then a few tiny ones that
    each start at 0. Summing completed and total over all layers seen, and keeping the highest value
    of each, stops the bar from jumping back when a new layer starts and adds to the total.
    """

    def __init__(self) -> None:
        self._layers: dict[str, tuple[int, int]] = {}
        self.completed = 0
        self.total = 0

    def update(self, digest: str, total: int, completed: int) -> tuple[int, int]:
        self._layers[digest] = (total, completed)
        self.total = max(self.total, sum(t for t, _ in self._layers.values()))
        self.completed = max(self.completed, sum(c for _, c in self._layers.values()))
        return self.completed, self.total

    def finish(self) -> tuple[int, int]:
        self.completed = self.total = max(self.total, self.completed)
        return self.completed, self.total


class OllamaAdmin:
    def __init__(self, base_url: str, transport: httpx.BaseTransport | None = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._transport = transport  # tests inject a fake HTTP transport

    def _client(self, timeout: httpx.Timeout | float) -> httpx.Client:
        return httpx.Client(base_url=self._base_url, timeout=timeout, transport=self._transport)

    def reachable(self) -> bool:
        try:
            with self._client(3) as client:
                return client.get("/api/tags").status_code == 200
        except httpx.HTTPError:
            return False

    def list_models(self) -> list[InstalledModel]:
        try:
            with self._client(10) as client:
                response = client.get("/api/tags")
                response.raise_for_status()
                models = response.json().get("models", [])
        except httpx.ConnectError as exc:
            raise OllamaError("ollama_unreachable") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaError("ollama_failed") from exc
        return [
            InstalledModel(m["name"], int(m.get("size", 0)), m.get("remote_host") or None)
            for m in models
        ]

    def installed(self, name: str) -> InstalledModel | None:
        wanted = name if ":" in name else f"{name}:latest"
        return next((m for m in self.list_models() if m.name == wanted), None)

    def delete(self, name: str) -> None:
        try:
            with self._client(30) as client:
                response = client.request("DELETE", "/api/delete", json={"model": name})
        except httpx.ConnectError as exc:
            raise OllamaError("ollama_unreachable") from exc
        except httpx.HTTPError as exc:
            raise OllamaError("ollama_failed") from exc
        if response.status_code == 404:
            raise OllamaError("model_not_found")
        if response.status_code >= 400:
            raise OllamaError("ollama_failed")

    def pull(
        self,
        name: str,
        on_progress: Callable[[int, int], None],
        cancel: threading.Event,
    ) -> None:
        """Download a model. `on_progress(completed, total)` gets bytes summed over all layers.

        Re-pulling after an interruption continues from the layers already on disk (Ollama's own
        behaviour; it is not documented, so the progress clamp does not depend on it).
        """
        progress = LayerProgress()
        timeout = httpx.Timeout(connect=5, read=120, write=30, pool=5)
        try:
            with (
                self._client(timeout) as client,
                client.stream(
                    "POST", "/api/pull", json={"model": name, "stream": True}
                ) as response,
            ):
                if response.status_code >= 400:
                    raise OllamaError(_pull_error_code(_error_text(response.read())))
                succeeded = self._read_stream(response, progress, on_progress, cancel)
        except httpx.ConnectError as exc:
            raise OllamaError("ollama_unreachable") from exc
        except (
            httpx.HTTPError
        ) as exc:  # timeouts and broken connections in the middle of a download
            raise OllamaError("network_error") from exc
        if not succeeded:
            raise OllamaError("network_error")  # the stream ended without "success"
        on_progress(*progress.finish())

    @staticmethod
    def _read_stream(
        response: httpx.Response,
        progress: LayerProgress,
        on_progress: Callable[[int, int], None],
        cancel: threading.Event,
    ) -> bool:
        for line in response.iter_lines():
            if cancel.is_set():
                raise Cancelled  # closing the connection stops the pull; partial layers are kept
            if not line:
                continue
            data: dict[str, Any] = json.loads(line)
            if "error" in data:
                raise OllamaError(_pull_error_code(str(data["error"])))
            if data.get("digest") and "total" in data:
                on_progress(
                    *progress.update(
                        data["digest"], int(data["total"]), int(data.get("completed", 0))
                    )
                )
            if data.get("status") == "success":
                return True
        return False


def _error_text(body: bytes) -> str:
    try:
        return str(json.loads(body).get("error", ""))
    except ValueError:
        return body.decode(errors="replace")


def _pull_error_code(message: str) -> str:
    low = message.lower()
    if "file does not exist" in low or "not found" in low:
        return "model_not_found"
    if "invalid model name" in low:
        return "invalid_model_name"
    if _NETWORK_HINTS.search(message):
        return "network_error"
    return "pull_failed"
