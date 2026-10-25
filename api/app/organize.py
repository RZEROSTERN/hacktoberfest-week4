"""Moving screenshots into place, with every step written down first.

The contract this module exists to keep: **no file is ever deleted, and every change can be
undone.** That is enforced by shape, not by care:

- The only filesystem operations here are "create a directory" and "move a file". There is no
  delete, no overwrite and no truncate anywhere in the module.
- A `Change` row is written and committed *before* the operation, then marked applied after it
  succeeds. A crash in between leaves a row that undo can check against the filesystem, rather
  than a move nobody recorded.
- A destination is chosen with `unique_path`, which counts up until it finds a free name, so a
  move can never land on top of something that is already there.
"""

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.errors import ApiError
from app.expiry import is_expired
from app.folders import ORGANIZED_DIR_NAME, is_inside
from app.models import Change, ChangeKind, Run, RunStatus, Screenshot, ShotStatus
from app.naming import destination_dir, stem_for, unique_path


@dataclass(frozen=True)
class Planned:
    screenshot_id: int
    from_path: Path
    to_path: Path
    review: bool
    reason: str  # "duplicate", "expired" or the category name


def _root_for(path: Path, folders: list[Path]) -> Path | None:
    """The watched folder a screenshot lives under, longest match first for nested folders."""
    for folder in sorted(folders, key=lambda f: len(str(f)), reverse=True):
        if is_inside(path, folder):
            return folder
    return None


class Organizer:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ------------------------------------------------------------------ plan

    def plan(self, run_id: int, folders: list[Path]) -> list[Planned]:
        """What organizing would do. Touches nothing on disk, and is safe to call repeatedly."""
        planned: list[Planned] = []
        taken: set[Path] = set()  # names this plan has already spoken for

        with Session(self._engine) as session:
            if session.get(Run, run_id) is None:
                raise ApiError(404, "run_not_found")
            shots = session.exec(
                select(Screenshot)
                .where(Screenshot.status == ShotStatus.ANALYZED)
                .order_by(col(Screenshot.captured_at), col(Screenshot.id))
            ).all()

            for shot in shots:
                current = Path(shot.current_path)
                if ORGANIZED_DIR_NAME in current.parts:
                    continue  # already filed by an earlier run
                root = _root_for(current, folders)
                if root is None:
                    continue  # the folder it came from is no longer watched

                expired = is_expired(shot.expiry_hint)
                review = shot.duplicate_of_id is not None or expired
                reason = (
                    "duplicate"
                    if shot.duplicate_of_id is not None
                    else "expired"
                    if expired
                    else (shot.category.value if shot.category else "other")
                )
                directory = destination_dir(root, ORGANIZED_DIR_NAME, shot.category, review)
                stem = stem_for(shot.captured_at, shot.slug or "screenshot")

                target = unique_path(directory, stem, current.suffix.lower())
                index = 2
                while target in taken:  # two shots in one plan wanting the same name
                    target = directory / f"{stem}-{index}{current.suffix.lower()}"
                    index += 1
                taken.add(target)

                assert shot.id is not None
                planned.append(Planned(shot.id, current, target, review, reason))
        return planned

    # --------------------------------------------------------------- execute

    def organize(self, run_id: int, folders: list[Path]) -> int:
        """Carry out the plan. Returns how many files were moved."""
        moved = 0
        for item in self.plan(run_id, folders):
            if self._apply(run_id, item):
                moved += 1
        self._finish(run_id)
        return moved

    def _apply(self, run_id: int, item: Planned) -> bool:
        source = item.from_path
        if not source.exists():
            self._mark_missing(item.screenshot_id)
            return False

        # The destination may have been taken since the plan was made.
        target = item.to_path
        if target.exists():
            target = unique_path(target.parent, target.stem, target.suffix)

        self._ensure_dir(run_id, target.parent)

        with Session(self._engine) as session:
            change = Change(
                run_id=run_id,
                screenshot_id=item.screenshot_id,
                kind=ChangeKind.MOVE,
                from_path=str(source),
                to_path=str(target),
            )
            session.add(change)
            session.commit()  # written down before it happens
            session.refresh(change)
            change_id = change.id

        shutil.move(str(source), str(target))

        with Session(self._engine) as session:
            change = session.get(Change, change_id)  # type: ignore[assignment]
            shot = session.get(Screenshot, item.screenshot_id)
            run = session.get(Run, run_id)
            assert change is not None and shot is not None and run is not None
            change.applied = True
            change.applied_at = datetime.now(UTC)
            shot.current_path = str(target)
            shot.expired = item.reason == "expired"
            run.organized += 1
            if item.review and item.reason == "expired":
                run.expired += 1
                run.reviewable_bytes += shot.size_bytes
            session.add_all([change, shot, run])
            session.commit()
        return True

    def _ensure_dir(self, run_id: int, directory: Path) -> None:
        """Create a folder, recording each level that did not exist, so undo can tidy up."""
        missing = []
        probe = directory
        while not probe.exists():
            missing.append(probe)
            probe = probe.parent
        if not missing:
            return
        directory.mkdir(parents=True, exist_ok=True)
        with Session(self._engine) as session:
            for created in reversed(missing):
                session.add(
                    Change(
                        run_id=run_id,
                        kind=ChangeKind.CREATE_DIR,
                        to_path=str(created),
                        applied=True,
                        applied_at=datetime.now(UTC),
                    )
                )
            session.commit()

    def _mark_missing(self, screenshot_id: int) -> None:
        with Session(self._engine) as session:
            shot = session.get(Screenshot, screenshot_id)
            if shot is not None:
                shot.status = ShotStatus.MISSING
                session.add(shot)
                session.commit()

    def _finish(self, run_id: int) -> None:
        with Session(self._engine) as session:
            run = session.get(Run, run_id)
            if run is not None:
                run.status = RunStatus.DONE
                run.finished_at = datetime.now(UTC)
                session.add(run)
                session.commit()
