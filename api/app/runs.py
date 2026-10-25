"""Starting and tracking a run. One run at a time, on one worker thread."""

import threading
from concurrent.futures import Executor
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.errors import ApiError, Cancelled
from app.indexing import Indexer
from app.models import Run, RunStatus, Screenshot, ShotStatus, WatchedFolder
from app.organize import Organizer, Planned
from app.settings_store import FIRST_RUN_APPROVED, get_flag, set_flag
from app.vision import Vision

ACTIVE = (RunStatus.SCANNING, RunStatus.ANALYZING, RunStatus.ORGANIZING)


class RunManager:
    def __init__(
        self,
        engine: Engine,
        indexer: Indexer,
        organizer: Organizer,
        executor: Executor,
        vision: Vision | None = None,
        pause: threading.Event | None = None,
    ) -> None:
        self._engine = engine
        self._indexer = indexer
        self._organizer = organizer
        self._executor = executor
        self._vision = vision
        # Shared with the indexer, which checks it between images. The desktop sets it when the
        # machine leaves the schedule window, goes on battery, or the user comes back.
        self._pause = pause or threading.Event()
        self._lock = threading.Lock()

    @property
    def paused(self) -> bool:
        return self._pause.is_set()

    def request_pause(self) -> None:
        """Stop after the image in flight. Never mid-file: a run always leaves a clean state."""
        self._pause.set()

    def resume(self) -> None:
        """Pick a paused run back up where it stopped."""
        self._pause.clear()
        with Session(self._engine) as session:
            run = session.exec(
                select(Run).where(Run.status == RunStatus.PAUSED).order_by(col(Run.id).desc())
            ).first()
            if run is None:
                raise ApiError(400, "no_run_in_progress")
            run_id = run.id
            run.status = RunStatus.ANALYZING
            session.add(run)
            session.commit()
        assert run_id is not None
        self._executor.submit(self._execute, run_id, self.folders())

    def recover(self) -> None:
        """A run that was going when the app stopped cannot be resumed from a half state."""
        with Session(self._engine) as session:
            for run in session.exec(select(Run).where(col(Run.status).in_(ACTIVE))).all():
                run.status = RunStatus.FAILED
                run.finished_at = datetime.now(UTC)
                session.add(run)
            # Anything left mid-analysis goes back in the queue; the cache means the work
            # already done is not repeated.
            session.commit()

    def folders(self) -> list[Path]:
        with Session(self._engine) as session:
            rows = session.exec(
                select(WatchedFolder).where(WatchedFolder.enabled == True)  # noqa: E712
            ).all()
            return [Path(r.path) for r in rows]

    def current(self) -> Run | None:
        with Session(self._engine) as session:
            return session.exec(select(Run).where(col(Run.status).in_(ACTIVE))).first()

    def start(self, manual: bool = True) -> Run:
        folders = self.folders()
        if not folders:
            raise ApiError(400, "folder_not_found")

        with self._lock:
            if self.current() is not None:
                raise ApiError(409, "run_in_progress")
            self._pause.clear()
            with Session(self._engine) as session:
                run = Run(manual=manual, status=RunStatus.SCANNING)
                session.add(run)
                session.commit()
                session.refresh(run)
                run_id = run.id
                created = run
        assert run_id is not None
        self._executor.submit(self._execute, run_id, folders)
        return created

    def _execute(self, run_id: int, folders: list[Path]) -> None:
        try:
            self._indexer.scan(run_id, folders)
            self._indexer.analyze_pending(run_id)
            # The very first sort is always shown before anything moves. Once the user has
            # approved once, later runs organize on their own.
            if get_flag(self._engine, FIRST_RUN_APPROVED):
                self._organizer.organize(run_id, folders)
        except Cancelled:
            pass  # the indexer already recorded the paused state
        except Exception:  # noqa: BLE001 - a run must never take the api down with it
            with Session(self._engine) as session:
                run = session.get(Run, run_id)
                if run is not None:
                    run.status = RunStatus.FAILED
                    run.finished_at = datetime.now(UTC)
                    session.add(run)
                    session.commit()
        finally:
            # The model is several gigabytes; it does not stay resident between runs.
            if self._vision is not None:
                self._vision.unload()

    def plan(self, run_id: int) -> list[Planned]:
        """What organizing would do to the files. Nothing on disk is touched."""
        return self._organizer.plan(run_id, self.folders())

    def approve(self, run_id: int) -> int:
        """The one-time approval of the first sort, which then carries out that run."""
        with Session(self._engine) as session:
            run = session.get(Run, run_id)
            if run is None:
                raise ApiError(404, "run_not_found")
            if run.status is not RunStatus.AWAITING_APPROVAL:
                raise ApiError(409, "already_approved")
        set_flag(self._engine, FIRST_RUN_APPROVED, True)
        return self._organizer.organize(run_id, self.folders())

    def preview(self, run_id: int) -> list[Screenshot]:
        """What the run would do, for the approval screen."""
        with Session(self._engine) as session:
            if session.get(Run, run_id) is None:
                raise ApiError(404, "run_not_found")
            return list(
                session.exec(
                    select(Screenshot)
                    .where(Screenshot.status == ShotStatus.ANALYZED)
                    .order_by(col(Screenshot.captured_at))
                ).all()
            )
