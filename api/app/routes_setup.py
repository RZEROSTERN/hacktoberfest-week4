"""The first-launch wizard, and model management afterwards.

Every refusal from the setup carries a stable code; `ERROR_MESSAGES` holds the English text.
Downloading is never started implicitly: the user names the model and asks for it.
"""

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.errors import ApiError
from app.setup import SetupError, SetupManager

router = APIRouter(prefix="/api/setup")

# Which refusals mean "you asked for something impossible" rather than "it went wrong".
_STATUS = {
    "setup_busy": 409,
    "model_in_use": 409,
    "nothing_to_resume": 400,
    "compat_needed": 400,
    "model_not_installed": 404,
    "invalid_model_name": 400,
    "cloud_model": 400,
    "not_enough_disk": 400,
}


class ModelIn(BaseModel):
    model: str


def _manager(request: Request) -> SetupManager:
    manager: SetupManager = request.app.state.setup
    return manager


def _refuse(exc: SetupError) -> ApiError:
    return ApiError(_STATUS.get(exc.code, 500), exc.code)


@router.get("/status")
def status(request: Request) -> dict[str, Any]:
    """Is the app ready, and if not, what is missing? What is recommended?"""
    return _manager(request).status()


@router.get("/progress")
def progress(request: Request) -> dict[str, Any]:
    """The wizard's progress screen: every step, with speed and time left on the download."""
    return _manager(request).snapshot()


@router.post("/start")
def start(request: Request, body: ModelIn) -> dict[str, Any]:
    """Download and check a model. The user has seen its size and license by now."""
    manager = _manager(request)
    try:
        manager.start(body.model)
    except SetupError as exc:
        raise _refuse(exc) from exc
    return manager.snapshot()


@router.post("/pause")
def pause(request: Request) -> dict[str, Any]:
    """Stop the download. What has arrived is kept, and resuming continues from there."""
    manager = _manager(request)
    manager.pause()
    return manager.snapshot()


@router.post("/resume")
def resume(request: Request) -> dict[str, Any]:
    manager = _manager(request)
    try:
        manager.resume()
    except SetupError as exc:
        raise _refuse(exc) from exc
    return manager.snapshot()


@router.get("/models")
def models(request: Request) -> list[dict[str, Any]]:
    """What is on this computer, and which of them this app has checked."""
    return _manager(request).models()


@router.post("/activate")
def activate(request: Request, body: ModelIn) -> dict[str, Any]:
    manager = _manager(request)
    try:
        manager.activate(body.model)
    except SetupError as exc:
        raise _refuse(exc) from exc
    return manager.status()


@router.post("/delete")
def delete(request: Request, body: ModelIn) -> list[dict[str, Any]]:
    """Remove a model from this computer. Never the one in use."""
    manager = _manager(request)
    try:
        manager.delete(body.model)
    except SetupError as exc:
        raise _refuse(exc) from exc
    return manager.models()
