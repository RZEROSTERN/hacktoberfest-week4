"""Searching the index.

What is searchable is decided by what was stored, not by a filter applied at query time. A
sensitive screenshot has no `extracted_text` row unless the user turned indexing on, so it
cannot be found by its contents here even by accident — there is nothing to match against.

Its one-sentence description is searchable, and is meant to be: "a password manager entry" is
how someone finds the screenshot again, and is not the secret itself.

Matching is a case-insensitive LIKE per term, all terms required. SQLite's FTS5 would rank
better, but it needs a second table kept in step with this one, and a few thousand rows do not
need it. If the index ever grows past that, this is the place to change.
"""

from dataclasses import dataclass

from sqlalchemy import func, or_
from sqlalchemy.engine import Engine
from sqlmodel import Session, col, select

from app.models import Screenshot, ShotStatus

MAX_RESULTS = 200
MAX_TERMS = 8


@dataclass(frozen=True)
class Hit:
    screenshot: Screenshot
    matched_text: bool  # the hit came from the stored text, not only the description


def terms_of(query: str) -> list[str]:
    """Words to require, lowercased. An empty query matches nothing rather than everything."""
    return [t for t in query.lower().split() if t][:MAX_TERMS]


def search(engine: Engine, query: str, limit: int = MAX_RESULTS) -> list[Hit]:
    terms = terms_of(query)
    if not terms:
        return []

    with Session(engine) as session:
        statement = select(Screenshot).where(Screenshot.status == ShotStatus.ANALYZED)
        for term in terms:
            pattern = f"%{term}%"
            statement = statement.where(
                or_(
                    func.lower(col(Screenshot.slug)).like(pattern),
                    func.lower(col(Screenshot.description)).like(pattern),
                    func.lower(col(Screenshot.extracted_text)).like(pattern),
                )
            )
        rows = session.exec(
            statement.order_by(col(Screenshot.captured_at).desc()).limit(limit)
        ).all()

        hits = []
        for row in rows:
            text = (row.extracted_text or "").lower()
            hits.append(Hit(screenshot=row, matched_text=any(t in text for t in terms)))
        return hits
