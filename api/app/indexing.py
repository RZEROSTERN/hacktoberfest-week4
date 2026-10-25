"""Scanning folders, hashing, finding duplicates and asking the model, one image at a time.

The order is deliberate and is what keeps the app cheap:

1. Walk the watched folders, skipping the folder Slothshot itself creates.
2. Hash the bytes. A file already in the index is skipped entirely, whatever its name or
   path now is, so nothing is ever analysed twice.
3. Perceptual-hash the new ones and compare against what is already indexed. A duplicate is
   settled here, without the model.
4. Only what is left reaches the model, one image at a time.

Nothing in this module logs file names, paths, image contents or extracted text.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.errors import ApiError, Cancelled
from app.folders import ORGANIZED_DIR_NAME
from app.images import captured_at, content_hash, hamming, is_supported, load_for_analysis
from app.models import Run, RunStatus, Screenshot, ShotStatus
from app.settings_store import INDEX_SENSITIVE_TEXT, get_flag
from app.vision import Vision

# Maximum differing bits between two difference hashes for one to count as a near duplicate.
#
# Calibrated, not guessed (see docs/DECISIONS.md). Across the fixture set and the maintainer's
# real captures: genuine duplicates, including a half-size resave, measure 0. The closest pair
# that is NOT a duplicate measures 7 in the fixtures and 8 in the real set, where the hardest
# case is two dashboard cards photographed five seconds apart with the same layout and
# different numbers. 4 sits in that gap with room on both sides.
DUPLICATE_DISTANCE = 4


@dataclass(frozen=True)
class Found:
    path: Path
    size_bytes: int


def iter_images(folders: list[Path]) -> Iterator[Found]:
    """Every readable image under the watched folders, excluding Slothshot's own output."""
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in sorted(folder.rglob("*")):
            if ORGANIZED_DIR_NAME in path.relative_to(folder).parts:
                continue  # our own output; re-reading it would sort already-sorted files again
            if not path.is_file() or path.is_symlink() or not is_supported(path):
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue  # vanished or unreadable between listing and stat
            if size > 0:
                yield Found(path=path, size_bytes=size)


class Indexer:
    """Runs one pass: scan, then analyse. Designed to be driven by a single worker thread."""

    def __init__(
        self,
        engine: Engine,
        vision: Vision,
        max_image_px: int,
        should_pause: Callable[[], bool] | None = None,
    ) -> None:
        self._engine = engine
        self._vision = vision
        self._max_px = max_image_px
        # The scheduler supplies this in step 7; until then a run never pauses itself.
        self._should_pause = should_pause or (lambda: False)

    # ---------------------------------------------------------------- scanning

    def scan(self, run_id: int, folders: list[Path]) -> int:
        """Record every image found. Returns how many are new and need analysis."""
        new = 0
        with Session(self._engine) as session:
            run = session.get(Run, run_id)
            if run is None:
                raise ApiError(404, "run_not_found")
            run.status = RunStatus.SCANNING

            for found in iter_images(folders):
                run.found += 1
                current = str(found.path)

                # Already tracked at this exact path: nothing new.
                tracked = session.exec(
                    select(Screenshot).where(Screenshot.current_path == current)
                ).first()
                if tracked is not None:
                    if tracked.status is ShotStatus.MISSING:
                        tracked.status = ShotStatus.PENDING
                        session.add(tracked)
                    continue

                digest = content_hash(found.path)
                # A row with these bytes whose file is no longer where it was: the user, or an
                # earlier run, moved it. Follow it rather than treating it as new.
                moved = next(
                    (
                        row
                        for row in session.exec(
                            select(Screenshot).where(Screenshot.content_hash == digest)
                        ).all()
                        if not Path(row.current_path).exists()
                    ),
                    None,
                )
                if moved is not None:
                    moved.current_path = current
                    if moved.status is ShotStatus.MISSING:
                        moved.status = ShotStatus.PENDING
                    session.add(moved)
                    continue

                # Either genuinely new, or a second copy of bytes already indexed. Both get a
                # row; the perceptual hash settles the second case during analysis, at distance
                # zero, without the model.

                session.add(
                    Screenshot(
                        content_hash=digest,
                        original_path=str(found.path),
                        current_path=str(found.path),
                        size_bytes=found.size_bytes,
                        captured_at=captured_at(found.path),
                        status=ShotStatus.PENDING,
                    )
                )
                new += 1
            session.add(run)
            session.commit()
        return new

    # --------------------------------------------------------------- analysing

    def analyze_pending(self, run_id: int) -> None:
        """Analyse every pending screenshot, one at a time, duplicates settled without the model."""
        with Session(self._engine) as session:
            run = session.get(Run, run_id)
            if run is None:
                raise ApiError(404, "run_not_found")
            run.status = RunStatus.ANALYZING
            session.add(run)
            session.commit()
            index_sensitive = get_flag(self._engine, INDEX_SENSITIVE_TEXT)

        while True:
            with Session(self._engine) as session:
                # Oldest first, so the screenshot the user actually took stays the original
                # and a later copy of it is the one that goes to Review.
                shot = session.exec(
                    select(Screenshot)
                    .where(Screenshot.status == ShotStatus.PENDING)
                    .order_by(col(Screenshot.captured_at), col(Screenshot.id))
                ).first()
                if shot is None:
                    break
                shot_id = shot.id
                path = Path(shot.current_path)
            assert shot_id is not None

            if self._should_pause():
                self._mark_run(run_id, RunStatus.PAUSED)
                raise Cancelled

            self._analyze_one(run_id, shot_id, path, index_sensitive)

        self._mark_run(run_id, RunStatus.AWAITING_APPROVAL)

    def _analyze_one(self, run_id: int, shot_id: int, path: Path, index_sensitive: bool) -> None:
        with Session(self._engine) as session:
            shot = session.get(Screenshot, shot_id)
            run = session.get(Run, run_id)
            assert shot is not None and run is not None

            if not path.exists():
                shot.status = ShotStatus.MISSING
                session.add(shot)
                session.commit()
                return

            try:
                loaded = load_for_analysis(path, self._max_px)
            except ApiError as exc:
                shot.status = ShotStatus.SKIPPED
                shot.skip_reason = exc.code
                run.skipped += 1
                session.add_all([shot, run])
                session.commit()
                return

            shot.width, shot.height = loaded.width, loaded.height
            shot.perceptual_hash = loaded.perceptual_hash

            twin = self._find_duplicate(session, shot)
            if twin is not None:
                # Settled without the model: the twin already carries the description.
                shot.duplicate_of_id = twin.id
                shot.status = ShotStatus.ANALYZED
                shot.analyzed_at = datetime.now(UTC)
                shot.category = twin.category
                shot.slug = twin.slug
                shot.description = twin.description
                shot.sensitive = twin.sensitive
                run.duplicates += 1
                run.reviewable_bytes += shot.size_bytes
                session.add_all([shot, run])
                session.commit()
                return

            try:
                result = self._vision.analyze(loaded.image)
            except ApiError as exc:
                shot.status = ShotStatus.SKIPPED
                shot.skip_reason = exc.code  # retry already happened inside the vision client
                run.skipped += 1
                session.add_all([shot, run])
                session.commit()
                return

            analysis = result.analysis
            shot.status = ShotStatus.ANALYZED
            shot.analyzed_at = datetime.now(UTC)
            shot.model_tag = result.model
            shot.prompt_version = result.prompt_version
            shot.slug = analysis.slug
            shot.category = analysis.category
            shot.description = analysis.description
            shot.sensitive = analysis.sensitive
            shot.expiry_hint = analysis.expiry_hint
            # The text of a sensitive screenshot is not stored unless the user allowed it.
            shot.extracted_text = (
                analysis.text if (not analysis.sensitive or index_sensitive) else None
            )
            run.analyzed += 1
            session.add_all([shot, run])
            session.commit()

    def _find_duplicate(self, session: Session, shot: Screenshot) -> Screenshot | None:
        """An already-analysed screenshot this one is an exact or near copy of."""
        if shot.perceptual_hash is None:
            return None
        candidates = session.exec(
            select(Screenshot).where(
                Screenshot.status == ShotStatus.ANALYZED,
                col(Screenshot.perceptual_hash).is_not(None),
                Screenshot.id != shot.id,
                col(Screenshot.duplicate_of_id).is_(None),
            )
        ).all()
        best: Screenshot | None = None
        best_distance = DUPLICATE_DISTANCE + 1
        for candidate in candidates:
            assert candidate.perceptual_hash is not None
            distance = hamming(shot.perceptual_hash, candidate.perceptual_hash)
            if distance <= DUPLICATE_DISTANCE and distance < best_distance:
                best, best_distance = candidate, distance
        return best

    def _mark_run(self, run_id: int, status: RunStatus) -> None:
        with Session(self._engine) as session:
            run = session.get(Run, run_id)
            if run is not None:
                run.status = status
                if status in (RunStatus.DONE, RunStatus.FAILED, RunStatus.CANCELLED):
                    run.finished_at = datetime.now(UTC)
                session.add(run)
                session.commit()
