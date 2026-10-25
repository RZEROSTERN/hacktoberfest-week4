"""Putting files back exactly where they were.

Undo replays the journal backwards. Two properties matter more than anything else here:

**It is all-or-nothing.** Every change is checked against the filesystem first, and only if
every one of them can be reversed does anything move. A user who is told "nothing was changed"
can rely on that, which is the whole point of offering undo on an app that rearranges their
files.

**It never deletes a file.** The only removal in this module is `rmdir` on a directory
Slothshot created and that is now empty, which cannot take a user's data with it.
"""

import contextlib
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.errors import ApiError
from app.models import Change, ChangeKind, Screenshot


def _pending(session: Session, *conditions: object) -> list[Change]:
    """Applied changes that have not been undone, newest first."""
    statement = select(Change).where(col(Change.applied).is_(True), col(Change.undone_at).is_(None))
    for condition in conditions:
        statement = statement.where(condition)  # type: ignore[arg-type]
    return list(session.exec(statement.order_by(col(Change.id).desc())).all())


def _check(changes: list[Change]) -> None:
    """Refuse the whole undo unless every move in it can be reversed."""
    # Paths this undo will free as it goes, so a chain of moves does not look blocked.
    freed: set[Path] = set()
    for change in changes:
        if change.kind is not ChangeKind.MOVE or change.from_path is None:
            continue
        current, original = Path(change.to_path), Path(change.from_path)
        if not current.exists():
            raise ApiError(409, "undo_blocked_missing")
        if original.exists() and original not in freed:
            raise ApiError(409, "undo_blocked_occupied")
        freed.add(current)


def _apply(session: Session, changes: list[Change]) -> int:
    moved = 0
    directories: list[Path] = []
    for change in changes:
        if change.kind is ChangeKind.CREATE_DIR:
            directories.append(Path(change.to_path))
        elif change.from_path is not None:
            Path(change.to_path).rename(Path(change.from_path))
            if change.screenshot_id is not None:
                shot = session.get(Screenshot, change.screenshot_id)
                if shot is not None:
                    shot.current_path = change.from_path
                    session.add(shot)
            moved += 1
        change.undone_at = datetime.now(UTC)
        session.add(change)

    # Folders Slothshot made, deepest first. Only ever removed when already empty, so this
    # cannot take anything of the user's with it.
    for directory in sorted(directories, key=lambda d: len(d.parts), reverse=True):
        # Fails harmlessly when someone put something in it, or it is already gone.
        with contextlib.suppress(OSError):
            directory.rmdir()
    session.commit()
    return moved


def undo_changes(engine: Engine, *conditions: object) -> int:
    with Session(engine) as session:
        changes = _pending(session, *conditions)
        if not changes:
            raise ApiError(400, "nothing_to_undo")
        _check(changes)
        return _apply(session, changes)


def undo_file(engine: Engine, screenshot_id: int) -> int:
    with Session(engine) as session:
        if session.get(Screenshot, screenshot_id) is None:
            raise ApiError(404, "screenshot_not_found")
    return undo_changes(engine, Change.screenshot_id == screenshot_id)


def undo_run(engine: Engine, run_id: int) -> int:
    return undo_changes(engine, Change.run_id == run_id)


def undo_everything(engine: Engine) -> int:
    return undo_changes(engine)
