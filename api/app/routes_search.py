from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

from app.models import Category
from app.search import MAX_RESULTS, Hit, search, terms_of
from app.summary import latest

router = APIRouter(prefix="/api")

SNIPPET_PAD = 60


class SearchHit(BaseModel):
    id: int
    path: str
    slug: str | None
    category: Category | None
    description: str | None
    sensitive: bool
    in_review: bool
    # A short window around the first matching word, so a result is recognisable without
    # sending the whole stored text to the screen.
    snippet: str | None


class SearchOut(BaseModel):
    query: str
    count: int
    hits: list[SearchHit]


class SummaryOut(BaseModel):
    run_id: int | None
    finished_at: str | None
    sorted_count: int
    skipped_count: int
    duplicates_waiting: int
    expired_waiting: int
    reclaimable_bytes: int
    total_indexed: int


def _snippet(hit: Hit, terms: list[str]) -> str | None:
    text = hit.screenshot.extracted_text
    if not hit.matched_text or not text:
        return None
    lowered = text.lower()
    at = min((lowered.find(t) for t in terms if lowered.find(t) >= 0), default=-1)
    if at < 0:
        return None
    start = max(0, at - SNIPPET_PAD)
    end = min(len(text), at + SNIPPET_PAD)
    return ("…" if start else "") + text[start:end].strip() + ("…" if end < len(text) else "")


@router.get("/search")
def run_search(
    request: Request,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=MAX_RESULTS, ge=1, le=MAX_RESULTS),
) -> SearchOut:
    """Search descriptions and whatever text was stored.

    The text of a sensitive screenshot was never stored unless the user allowed it, so it
    cannot be matched here. Its description still can be, which is how the screenshot is
    found again without the secret being in the index.
    """
    terms = terms_of(q)
    hits = search(request.app.state.engine, q, limit)
    return SearchOut(
        query=q,
        count=len(hits),
        hits=[
            SearchHit(
                id=h.screenshot.id or 0,
                path=h.screenshot.current_path,
                slug=h.screenshot.slug,
                category=h.screenshot.category,
                description=h.screenshot.description,
                sensitive=h.screenshot.sensitive,
                in_review="Review" in h.screenshot.current_path,
                snippet=_snippet(h, terms),
            )
            for h in hits
        ],
    )


@router.get("/summary")
def run_summary(request: Request) -> SummaryOut:
    """The morning card."""
    summary = latest(request.app.state.engine)
    return SummaryOut(**summary.__dict__)
