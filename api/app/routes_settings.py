"""Settings the user can change, and the controls the desktop shell drives.

The schedule itself is enforced in the desktop shell, which is the only part that can see
whether the machine is idle or on battery. It is stored here so the web app can edit it and
so it survives a restart.
"""

import json

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from sqlalchemy.engine import Engine

from app.runs import RunManager
from app.settings_store import (
    INDEX_SENSITIVE_TEXT,
    SCHEDULE,
    VISION_MODEL,
    get_flag,
    get_setting,
    set_flag,
    set_setting,
)

router = APIRouter(prefix="/api")


class ScheduleIn(BaseModel):
    enabled: bool = True
    windowStart: str = Field(default="23:00", pattern=r"^\d{1,2}:\d{2}$")
    windowEnd: str = Field(default="07:00", pattern=r"^\d{1,2}:\d{2}$")
    requireIdle: bool = True
    idleThresholdSeconds: int = Field(default=300, ge=30, le=86_400)
    pauseOnBattery: bool = True


class SettingsOut(BaseModel):
    vision_model: str | None
    index_sensitive_text: bool
    max_image_px: int
    schedule: ScheduleIn
    paused: bool


class SettingsIn(BaseModel):
    index_sensitive_text: bool | None = None
    schedule: ScheduleIn | None = None


def _engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


def _manager(request: Request) -> RunManager:
    manager: RunManager = request.app.state.runs
    return manager


def _schedule(engine: Engine) -> ScheduleIn:
    stored = get_setting(engine, SCHEDULE)
    if not stored:
        return ScheduleIn()
    try:
        return ScheduleIn.model_validate(json.loads(stored))
    except (ValueError, TypeError):
        # A setting written by an older version should not stop the app starting.
        return ScheduleIn()


def _read(request: Request) -> SettingsOut:
    engine = _engine(request)
    return SettingsOut(
        vision_model=get_setting(engine, VISION_MODEL),
        index_sensitive_text=get_flag(engine, INDEX_SENSITIVE_TEXT),
        max_image_px=request.app.state.settings.max_image_px,
        schedule=_schedule(engine),
        paused=_manager(request).paused,
    )


@router.get("/settings")
def read_settings(request: Request) -> SettingsOut:
    return _read(request)


@router.put("/settings")
def write_settings(request: Request, body: SettingsIn) -> SettingsOut:
    engine = _engine(request)
    if body.index_sensitive_text is not None:
        set_flag(engine, INDEX_SENSITIVE_TEXT, body.index_sensitive_text)
    if body.schedule is not None:
        set_setting(engine, SCHEDULE, body.schedule.model_dump_json())
    return _read(request)


@router.post("/runs/pause")
def pause_run(request: Request) -> SettingsOut:
    """Stop after the image in flight. A run never stops mid-file."""
    _manager(request).request_pause()
    return _read(request)


@router.post("/runs/resume")
def resume_run(request: Request) -> SettingsOut:
    """Pick a paused run back up where it stopped."""
    _manager(request).resume()
    return _read(request)
