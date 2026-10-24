from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.errors import ApiError
from app.folders import detect_screenshot_folders, validate_folder
from app.models import WatchedFolder

router = APIRouter(prefix="/api/folders")


class FolderIn(BaseModel):
    path: str


class FolderOut(BaseModel):
    id: int
    path: str
    enabled: bool
    detected: bool


def _engine(request: Request) -> Engine:
    engine: Engine = request.app.state.engine
    return engine


def _watched(session: Session) -> list[WatchedFolder]:
    return list(session.exec(select(WatchedFolder)).all())


@router.get("")
def list_folders(request: Request) -> list[FolderOut]:
    with Session(_engine(request)) as session:
        return [
            FolderOut(id=f.id or 0, path=f.path, enabled=f.enabled, detected=f.detected)
            for f in _watched(session)
        ]


@router.get("/detected")
def detected(request: Request) -> list[str]:
    """What this OS suggests, so the first-launch screen can offer it. Nothing is added yet."""
    with Session(_engine(request)) as session:
        known = {f.path for f in _watched(session)}
    return [str(p) for p in detect_screenshot_folders() if str(p) not in known]


@router.post("", status_code=201)
def add_folder(request: Request, body: FolderIn) -> FolderOut:
    with Session(_engine(request)) as session:
        existing = _watched(session)
        resolved = validate_folder(Path(body.path), [Path(f.path) for f in existing])
        folder = WatchedFolder(path=str(resolved))
        session.add(folder)
        session.commit()
        session.refresh(folder)
        return FolderOut(
            id=folder.id or 0, path=folder.path, enabled=folder.enabled, detected=folder.detected
        )


@router.delete("/{folder_id}", status_code=204)
def remove_folder(request: Request, folder_id: int) -> None:
    """Stops watching a folder. Files already sorted are untouched; undo handles those."""
    with Session(_engine(request)) as session:
        folder = session.get(WatchedFolder, folder_id)
        if folder is None:
            raise ApiError(404, "folder_not_found")
        session.delete(folder)
        session.commit()
