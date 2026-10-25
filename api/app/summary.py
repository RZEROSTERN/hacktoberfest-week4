"""The morning card: what happened overnight, in numbers.

Deliberately small. It answers three questions and no others: how many screenshots were
sorted, how many things are waiting in Review, and how much space those would free if the user
decided to delete them by hand. Slothshot never deletes anything itself, so the last number is
information, not an offer.
"""

from dataclasses import dataclass

from sqlalchemy.engine import Engine
from sqlmodel import Session, col, func, select

from app.models import Run, RunStatus, Screenshot, ShotStatus


@dataclass(frozen=True)
class Summary:
    run_id: int | None
    finished_at: str | None
    sorted_count: int
    skipped_count: int
    duplicates_waiting: int
    expired_waiting: int
    reclaimable_bytes: int
    total_indexed: int


def latest(engine: Engine) -> Summary:
    with Session(engine) as session:
        run = session.exec(
            select(Run).where(Run.status == RunStatus.DONE).order_by(col(Run.finished_at).desc())
        ).first()

        # Counted from the index rather than the run, so the card reflects everything still
        # waiting in Review, not only what the most recent run put there.
        waiting = session.exec(
            select(Screenshot).where(
                Screenshot.status == ShotStatus.ANALYZED,
                col(Screenshot.current_path).contains("Review"),
            )
        ).all()
        duplicates = sum(1 for s in waiting if s.duplicate_of_id is not None)
        expired = sum(1 for s in waiting if s.expired and s.duplicate_of_id is None)
        reclaimable = sum(s.size_bytes for s in waiting)

        total = session.exec(select(func.count()).select_from(Screenshot)).one()

        return Summary(
            run_id=run.id if run else None,
            finished_at=run.finished_at.isoformat() if run and run.finished_at else None,
            sorted_count=run.organized if run else 0,
            skipped_count=run.skipped if run else 0,
            duplicates_waiting=duplicates,
            expired_waiting=expired,
            reclaimable_bytes=reclaimable,
            total_indexed=int(total),
        )
