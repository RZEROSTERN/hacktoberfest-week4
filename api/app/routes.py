from fastapi import APIRouter, Request
from sqlalchemy.engine import Engine

from app.settings_store import (
    INDEX_SENSITIVE_TEXT,
    VISION_MODEL,
    get_flag,
    get_setting,
)

router = APIRouter(prefix="/api")


def _engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


@router.get("/status")
def status(request: Request) -> dict[str, object]:
    """What the web app needs on load: whether a model is chosen and how text is handled."""
    engine = _engine(request)
    return {
        "vision_model": get_setting(engine, VISION_MODEL),
        "index_sensitive_text": get_flag(engine, INDEX_SENSITIVE_TEXT),
        "max_image_px": request.app.state.settings.max_image_px,
    }
