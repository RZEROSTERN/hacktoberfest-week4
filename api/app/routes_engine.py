"""Whether the local model engine is up, and what it holds.

This is what the first-launch wizard asks before offering a download, and what the packaged
build's smoke test uses to prove the api and the bundled Ollama can actually talk to each
other across a process boundary on each platform.
"""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.catalog import VisionModel, load_catalog
from app.ollama import ModelEngine, OllamaAdmin, OllamaError
from app.settings_store import VISION_MODEL, get_setting

router = APIRouter(prefix="/api")


class InstalledOut(BaseModel):
    name: str
    size_bytes: int


class EngineOut(BaseModel):
    reachable: bool
    installed: list[InstalledOut]
    selected: str | None
    selected_installed: bool
    recommended: list[VisionModel]


def _engine_client(request: Request) -> ModelEngine:
    existing: ModelEngine | None = getattr(request.app.state, "ollama", None)
    if existing is not None:
        return existing
    return OllamaAdmin(request.app.state.settings.ollama_url)


@router.get("/engine")
def engine_status(request: Request) -> EngineOut:
    client = _engine_client(request)
    selected = get_setting(request.app.state.engine, VISION_MODEL)
    catalog = load_catalog()

    if not client.reachable():
        return EngineOut(
            reachable=False,
            installed=[],
            selected=selected,
            selected_installed=False,
            recommended=catalog.vision,
        )

    try:
        models = client.list_models()
    except OllamaError:
        models = []

    # Ollama reports a bare name as `name:latest`, so compare the way it stores them.
    wanted = (
        selected if (selected and ":" in selected) else f"{selected}:latest" if selected else None
    )
    return EngineOut(
        reachable=True,
        installed=[InstalledOut(name=m.name, size_bytes=m.size_bytes) for m in models],
        selected=selected,
        selected_installed=any(m.name == wanted for m in models),
        recommended=catalog.vision,
    )
