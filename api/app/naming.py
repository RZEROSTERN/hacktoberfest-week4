"""Building the name and the place a screenshot is moved to.

Every name starts with the capture date, which has a useful side effect: a filename can never
begin with a Windows reserved device name (CON, PRN, AUX, NUL, COM1...), because it always
begins with a digit.
"""

from datetime import datetime, tzinfo
from pathlib import Path

from app.models import Category

# Long enough to stay descriptive, short enough that the whole path stays well inside the
# limits of all three filesystems even under a deep folder.
MAX_STEM = 96
REVIEW_DIR_NAME = "Review"


def stem_for(captured_at: datetime | None, slug: str, tz: tzinfo | None = None) -> str:
    """`2026-09-07-northgate-market-receipt`, or just the slug when the date is unknown.

    The date is the one the user would say it was. Capture times are stored in UTC, so an
    evening screenshot west of Greenwich would otherwise be filed under tomorrow.

    `tz` defaults to this machine's zone, which is the user's zone for a desktop app. It is a
    parameter only so the behaviour can be pinned in a test without depending on where the
    test happens to run.
    """
    cleaned = slug.strip("-") or "screenshot"
    if captured_at is None:
        return cleaned[:MAX_STEM].rstrip("-")
    local = captured_at.astimezone(tz) if captured_at.tzinfo else captured_at
    return f"{local.date().isoformat()}-{cleaned}"[:MAX_STEM].rstrip("-")


def destination_dir(
    root: Path, organized_name: str, category: Category | None, review: bool
) -> Path:
    """`<watched folder>/Slothshot/<category>/`, or the Review folder."""
    base = root / organized_name
    if review:
        return base / REVIEW_DIR_NAME
    return base / (category.value if category else Category.OTHER.value)


def unique_path(directory: Path, stem: str, suffix: str) -> Path:
    """A path in `directory` that nothing occupies yet.

    A collision is resolved by counting up rather than by overwriting: two different
    screenshots taken the same day can easily earn the same description.
    """
    candidate = directory / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        candidate = directory / f"{stem}-{index}{suffix}"
        if not candidate.exists():
            return candidate
    # Practically unreachable; falling back to the microsecond keeps it deterministic enough
    # to be debuggable and still never overwrites.
    return directory / f"{stem}-{datetime.now().strftime('%H%M%S%f')}{suffix}"
