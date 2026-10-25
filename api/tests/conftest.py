from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app
from app.schemas import Analysis
from app.vision import VisionResult


class ScriptedVision:
    """Stands in for the model. Answers every image the same way unless told otherwise."""

    def __init__(self, answer: Analysis | None = None) -> None:
        # Lets a test act at a known point in a run, without sleeping and hoping.
        self.on_call: Callable[[int], None] | None = None
        self.answer = answer or Analysis.model_validate(
            {"slug": "a-screenshot", "category": "other", "description": "d", "text": "t"}
        )
        self.calls = 0
        self.unloads = 0

    def analyze(self, image: Image.Image) -> VisionResult:
        self.calls += 1
        if self.on_call is not None:
            self.on_call(self.calls)
        return VisionResult(
            analysis=self.answer,
            seconds=0.01,
            retried=False,
            model="fake:1",
            prompt_version="analyze.v1",
        )

    def unload(self) -> None:
        self.unloads += 1


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        port=8765,
        data_dir=tmp_path / "data",
        models_dir=tmp_path / "models",
        ollama_url="http://127.0.0.1:11434",
    )


@pytest.fixture
def vision() -> ScriptedVision:
    return ScriptedVision()


@pytest.fixture
def client(settings: Settings, vision: ScriptedVision) -> Iterator[TestClient]:
    with TestClient(create_app(settings, vision=vision)) as test_client:
        yield test_client
