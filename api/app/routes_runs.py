from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlmodel import Session, col, select

from app.errors import ApiError
from app.models import Category, Run
from app.runs import RunManager
from app.undo import undo_run

router = APIRouter(prefix="/api/runs")


class RunOut(BaseModel):
    id: int
    status: str
    manual: bool
    found: int
    analyzed: int
    skipped: int
    organized: int
    duplicates: int
    expired: int
    reviewable_bytes: int

    @classmethod
    def of(cls, run: Run) -> "RunOut":
        return cls(
            id=run.id or 0,
            status=run.status.value,
            manual=run.manual,
            found=run.found,
            analyzed=run.analyzed,
            skipped=run.skipped,
            organized=run.organized,
            duplicates=run.duplicates,
            expired=run.expired,
            reviewable_bytes=run.reviewable_bytes,
        )


class PreviewItem(BaseModel):
    id: int
    current_path: str
    slug: str | None
    category: Category | None
    description: str | None
    sensitive: bool
    duplicate_of_id: int | None
    size_bytes: int


def _manager(request: Request) -> RunManager:
    manager: RunManager = request.app.state.runs
    return manager


@router.post("", status_code=201)
def start_run(request: Request) -> RunOut:
    return RunOut.of(_manager(request).start(manual=True))


@router.get("")
def list_runs(request: Request) -> list[RunOut]:
    engine = request.app.state.engine
    with Session(engine) as session:
        rows = session.exec(select(Run).order_by(col(Run.started_at).desc())).all()
        return [RunOut.of(r) for r in rows]


@router.get("/current")
def current_run(request: Request) -> RunOut | None:
    run = _manager(request).current()
    return RunOut.of(run) if run else None


@router.get("/{run_id}")
def get_run(request: Request, run_id: int) -> RunOut:
    engine = request.app.state.engine
    with Session(engine) as session:
        run = session.get(Run, run_id)
        if run is None:
            raise ApiError(404, "run_not_found")
        return RunOut.of(run)


@router.get("/{run_id}/preview")
def preview(request: Request, run_id: int) -> list[PreviewItem]:
    """What the run found, before anything on disk is touched."""
    return [
        PreviewItem(
            id=s.id or 0,
            current_path=s.current_path,
            slug=s.slug,
            category=s.category,
            description=s.description,
            sensitive=s.sensitive,
            duplicate_of_id=s.duplicate_of_id,
            size_bytes=s.size_bytes,
        )
        for s in _manager(request).preview(run_id)
    ]


class PlanItem(BaseModel):
    screenshot_id: int
    from_path: str
    to_path: str
    review: bool
    reason: str


class UndoOut(BaseModel):
    restored: int


@router.get("/{run_id}/plan")
def plan(request: Request, run_id: int) -> list[PlanItem]:
    """Exactly what would move, and where. Nothing on disk is touched by asking."""
    return [
        PlanItem(
            screenshot_id=p.screenshot_id,
            from_path=str(p.from_path),
            to_path=str(p.to_path),
            review=p.review,
            reason=p.reason,
        )
        for p in _manager(request).plan(run_id)
    ]


@router.post("/{run_id}/approve")
def approve(request: Request, run_id: int) -> RunOut:
    """Approve the first sort. Later runs organize without asking again."""
    manager = _manager(request)
    manager.approve(run_id)
    engine = request.app.state.engine
    with Session(engine) as session:
        run = session.get(Run, run_id)
        assert run is not None
        return RunOut.of(run)


@router.post("/{run_id}/undo")
def undo_one_run(request: Request, run_id: int) -> UndoOut:
    return UndoOut(restored=undo_run(request.app.state.engine, run_id))
