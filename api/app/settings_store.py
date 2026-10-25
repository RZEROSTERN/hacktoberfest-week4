from collections.abc import Callable

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.models import AppSetting

VISION_MODEL = "vision_model"
# Off by default: the text of a sensitive screenshot is not stored or indexed unless the user
# turns this on. See .claude/rules/api.md.
INDEX_SENSITIVE_TEXT = "index_sensitive_text"
FIRST_RUN_APPROVED = "first_run_approved"
# The schedule, as JSON. Stored here so it survives a restart; enforced in the desktop shell,
# which is the only part that can see idleness and power state.
SCHEDULE = "schedule"


def get_setting(engine: Engine, key: str) -> str | None:
    with Session(engine) as session:
        row = session.get(AppSetting, key)
        return row.value if row else None


def set_setting(engine: Engine, key: str, value: str) -> None:
    with Session(engine) as session:
        session.merge(AppSetting(key=key, value=value))
        session.commit()


def delete_setting(engine: Engine, key: str) -> None:
    with Session(engine) as session:
        row = session.get(AppSetting, key)
        if row is not None:
            session.delete(row)
            session.commit()


def get_flag(engine: Engine, key: str) -> bool:
    return get_setting(engine, key) == "1"


def set_flag(engine: Engine, key: str, value: bool) -> None:
    set_setting(engine, key, "1" if value else "0")


def compat_key(model: str) -> str:
    """Setting that records that a model passed the image compatibility check."""
    return f"compat_ok:{model}"


def seed_setting(engine: Engine, key: str, value: str | None) -> None:
    """Store `value` only if nothing is stored yet (used to seed the model from the environment)."""
    if value and get_setting(engine, key) is None:
        set_setting(engine, key, value)


def vision_model_getter(engine: Engine) -> Callable[[], str | None]:
    return lambda: get_setting(engine, VISION_MODEL)
