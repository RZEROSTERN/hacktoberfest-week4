from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.ollama import InstalledModel, OllamaError
from tests.conftest import ScriptedVision


class FakeEngine:
    def __init__(
        self,
        reachable: bool = True,
        models: list[InstalledModel] | None = None,
        failing: bool = False,
    ) -> None:
        self._reachable = reachable
        self._models = models or []
        self._failing = failing

    def reachable(self) -> bool:
        return self._reachable

    def list_models(self) -> list[InstalledModel]:
        if self._failing:
            raise OllamaError("ollama_failed")
        return self._models

    def installed(self, name: str) -> InstalledModel | None:
        return next((m for m in self._models if m.name == name), None)

    def delete(self, name: str) -> None: ...

    def pull(self, name: str, on_progress: Callable[[int, int], None], cancel: Any) -> None: ...


@pytest.fixture
def engine_client(settings: Settings) -> Callable[[FakeEngine], TestClient]:
    def make(engine: FakeEngine) -> TestClient:
        app = create_app(settings, vision=ScriptedVision())
        app.state.ollama = engine
        return TestClient(app)

    return make


def test_reports_the_engine_being_down_without_failing(
    engine_client: Callable[[FakeEngine], TestClient],
) -> None:
    with engine_client(FakeEngine(reachable=False)) as client:
        body = client.get("/api/engine").json()
    assert body["reachable"] is False
    assert body["installed"] == []
    # The recommended list is still offered, so the wizard can show what to download.
    assert len(body["recommended"]) >= 1


def test_lists_what_is_installed(engine_client: Callable[[FakeEngine], TestClient]) -> None:
    models = [InstalledModel("qwen3-vl:2b-instruct", 1_900_000_000, None)]
    with engine_client(FakeEngine(models=models)) as client:
        body = client.get("/api/engine").json()
    assert body["reachable"] is True
    assert body["installed"][0]["name"] == "qwen3-vl:2b-instruct"


def test_says_whether_the_chosen_model_is_actually_there(
    engine_client: Callable[[FakeEngine], TestClient], settings: Settings
) -> None:
    settings.vision_model = "qwen3-vl:2b-instruct"
    models = [InstalledModel("qwen3-vl:2b-instruct", 1_900_000_000, None)]
    with engine_client(FakeEngine(models=models)) as client:
        body = client.get("/api/engine").json()
    assert body["selected"] == "qwen3-vl:2b-instruct"
    assert body["selected_installed"] is True


def test_a_chosen_model_that_is_missing_is_reported_as_missing(
    engine_client: Callable[[FakeEngine], TestClient], settings: Settings
) -> None:
    settings.vision_model = "qwen3-vl:2b-instruct"
    with engine_client(FakeEngine(models=[])) as client:
        body = client.get("/api/engine").json()
    assert body["selected_installed"] is False


def test_an_engine_error_does_not_take_the_endpoint_down(
    engine_client: Callable[[FakeEngine], TestClient],
) -> None:
    with engine_client(FakeEngine(failing=True)) as client:
        response = client.get("/api/engine")
    assert response.status_code == 200
    assert response.json()["installed"] == []
