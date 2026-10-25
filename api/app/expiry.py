"""Deciding whether a screenshot's moment has already passed.

The model returns `expiry_hint` in its own words ("flight departs 4 Feb 2026", "one-time code,
minutes"). Turning that into a yes or no is done here, in code, and deliberately
**conservatively**: only an unambiguous, fully specified date that is already past counts as
expired. Anything else is left alone.

Getting this wrong in one direction moves a screenshot the user still needs into Review, where
it is still findable and still undoable. Getting it wrong in the other direction leaves a stale
screenshot filed normally, which costs nothing. The cautious default is therefore "not
expired", and no date is ever guessed from a partial one: "2 dic" without a year stays
unresolved, because assuming a year is how a boarding pass from last month gets treated as next
year's.
"""

import re
from datetime import date

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# 2026-02-04
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
# 4 February 2026  /  4 Feb 2026
_DMY = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\.?\s+(\d{4})\b")
# February 4, 2026  /  Feb 4 2026
_MDY = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})\b")


def _valid(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def find_date(text: str) -> date | None:
    """The first fully specified calendar date in `text`, or None.

    A date without a year is not a date for this purpose.
    """
    iso = _ISO.search(text)
    if iso:
        found = _valid(int(iso[1]), int(iso[2]), int(iso[3]))
        if found:
            return found

    dmy = _DMY.search(text)
    if dmy:
        month = MONTHS.get(dmy[2].lower())
        if month:
            found = _valid(int(dmy[3]), month, int(dmy[1]))
            if found:
                return found

    mdy = _MDY.search(text)
    if mdy:
        month = MONTHS.get(mdy[1].lower())
        if month:
            found = _valid(int(mdy[3]), month, int(mdy[2]))
            if found:
                return found
    return None


def is_expired(expiry_hint: str | None, today: date | None = None) -> bool:
    """True only when the hint names a complete date that is already past."""
    if not expiry_hint:
        return False
    found = find_date(expiry_hint)
    if found is None:
        return False
    return found < (today or date.today())
