from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.undo import undo_everything, undo_file

router = APIRouter(prefix="/api")


class UndoResult(BaseModel):
    restored: int


@router.post("/screenshots/{screenshot_id}/undo")
def undo_single_file(request: Request, screenshot_id: int) -> UndoResult:
    """Put one screenshot back where it was found."""
    return UndoResult(restored=undo_file(request.app.state.engine, screenshot_id))


@router.post("/undo/everything")
def undo_all(request: Request) -> UndoResult:
    """Put every screenshot Slothshot has ever moved back where it was found."""
    return UndoResult(restored=undo_everything(request.app.state.engine))
